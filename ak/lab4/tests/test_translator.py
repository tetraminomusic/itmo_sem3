# tests/test_translator.py
import os
import sys

import pytest

# Добавляем папку src в путь поиска
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import translator
from isa import Opcode
from parser import StringLiteral, parse, tokenize


@pytest.fixture(autouse=True)
def reset_translator():
    translator.program = []
    translator.symbol_table = {}
    translator.data_memory = {}
    translator.functions = {}
    translator.local_vars = {}
    translator.current_reg = 1
    translator.label_counter = 0
    translator.data_address_counter = 100
    translator.interrupt_handler = None


def test_unclosed_parenthesis():
    """Ошибка: забытая закрывающая скобка."""
    code = "(+ 1 (* 2 3)"
    with pytest.raises(SyntaxError, match="Ожидалась закрывающая скобка"):
        parse(tokenize(code))


def test_extra_closing_parenthesis():
    """Ошибка: лишняя закрывающая скобка."""
    code = "(+ 1 2) )"
    tokens = tokenize(code)
    parse(tokens)  # спарсили (+ 1 2)
    with pytest.raises(SyntaxError, match="Неожиданная закрывающая скобка"):
        parse(tokens)  # наткнулись на лишнюю ')'


def test_semicolon_inside_string():
    """Точка с запятой внутри строки в кавычках НЕ должна считаться комментарием."""
    code = '(setq text "hello;world")'
    tokens = tokenize(code)
    ast = parse(tokens)
    assert isinstance(ast[2], StringLiteral)
    assert ast[2].text == "hello;world"


def test_empty_string_literal():
    """Пустая строка Pascal должна иметь длину 0."""
    code = '(setq empty "")'
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    # По адресу 101 должна лежать длина 0
    assert translator.data_memory[101] == 0


def test_deeply_nested_expressions():
    """Глубокая вложенность скобок (в пределах лимита регистров)."""
    code = "(+ 1 (+ 2 (+ 3 (+ 4 5))))"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    assert (
        res_reg == "R1"
    )  # Благодаря освобождению регистров всё должно свернуться в R1


def test_if_with_variable_predicate():

    code = """
    (progn
        (setq p 1)
        (setq a (if p 10 20))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Проверяем, что сгенерировалась команда сравнения переменной с нулем R0: CMP reg, R0
    cmp_with_zero = [
        instr
        for instr in clean_code
        if instr.opcode == Opcode.CMP and "R0" in instr.args
    ]
    assert len(cmp_with_zero) == 1, "Ожидалось сравнение переменной p с нулем R0"

    # Проверяем, что для перехода в else используется команда JZ
    jz_jumps = [instr for instr in clean_code if instr.opcode == Opcode.JZ]
    assert len(jz_jumps) == 1, "Ожидался прыжок в else по команде JZ"


def test_if_with_number_literal_predicate():
    code = "(if 1 100 200)"
    ast = parse(tokenize(code))
    _ = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Условие-число должно сравниться с нулем и сгенерировать JZ
    assert Opcode.CMP in [instr.opcode for instr in clean_code]
    assert Opcode.JZ in [instr.opcode for instr in clean_code]
    assert clean_code[-1].opcode == Opcode.HLT


def test_variadic_addition():
    code = "(+ 1 2 3 4 5)"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Должно сгенерироваться 4 инструкции ADD
    adds = [instr for instr in clean_code if instr.opcode == Opcode.ADD]
    assert len(adds) == 4
    assert res_reg == "R1"


def test_binary_op_wrong_arity():
    code = "(- 1 2 3)"  # Заменили '+' на '-'
    with pytest.raises(SyntaxError, match="требует ровно 2 операнда"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_aref_read_pascal_string():
    """aref должен генерировать ADD (смещение) и LD (чтение) из памяти."""
    code = """
    (progn
        (setq s "ITMO")
        (setq len (aref s 0))    ; чтение длины
        (setq char (aref s 1))   ; чтение первого символа
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Проверяем, что сгенерировались инструкции LD для чтения со смещением
    loads = [instr for instr in clean_code if instr.opcode == Opcode.LD]
    assert len(loads) >= 2


def test_aset_modify_memory():
    """aset должен вычислять адрес через ADD и записывать значение через ST."""
    code = """
    (progn
        (setq s "ABC")
        (aset s 1 88) ; заменяем символ по индексу 1 на код 88 ('X')
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    stores = [instr for instr in clean_code if instr.opcode == Opcode.ST]
    assert len(stores) >= 2  # запись переменной и запись через aset


def test_definterrupt_and_vector_table_linking():
    """
    Проверка адресной карты векторов:
    Адрес 0000 -> JMP _start
    Адрес 0001 -> JMP на обработчик прерывания
    Тело обработчика завершается командой IRET.
    """
    code = """
    (progn
        (definterrupt on_key ()
            (out 1 (in 0)))

        (setq x 100)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Адрес 0 обязан быть безусловным прыжком JMP на начало программы
    assert clean_code[0].opcode == Opcode.JMP

    # Адрес 1 обязан быть прыжком JMP на обработчик прерывания
    assert clean_code[1].opcode == Opcode.JMP

    # В коде обязана присутствовать инструкция возврата из прерывания IRET
    assert Opcode.IRET in [instr.opcode for instr in clean_code]


def test_vector_table_fallback_iret():
    """Если definterrupt не объявлен, по адресу 0001 должна стоять заглушка IRET."""
    code = "(setq a 42)"
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    assert clean_code[0].opcode == Opcode.JMP  # Вектор 0: JMP _start
    assert clean_code[1].opcode == Opcode.IRET  # Вектор 1: безопасная заглушка IRET


def test_print_builtin():
    """Команда (print expr) должна выводить значение в порт 1 и возвращать его."""
    code = "(print 65)"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Проверяем наличие команды OUT в порт 1
    out_instrs = [i for i in clean_code if i.opcode == Opcode.OUT and i.args[0] == 1]
    assert len(out_instrs) == 1
    assert res_reg == "R1"


def test_inc_and_dec_opcodes():
    """Проверка генерации машинных команд INC и DEC."""
    code = """
    (progn
        (setq a 10)
        (setq b (inc a))
        (setq c (dec b))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    opcodes = {i.opcode for i in clean_code}
    assert Opcode.INC in opcodes
    assert Opcode.DEC in opcodes


def test_aref_and_aset_syntax_errors():
    """Валидация количества аргументов у aref и aset."""
    with pytest.raises(SyntaxError, match="Команда 'aref' требует 2 аргумента"):
        parse_tree = parse(tokenize("(aref s)"))
        translator.compile_expr(parse_tree)

    with pytest.raises(SyntaxError, match="Команда 'aset' требует 3 аргумента"):
        parse_tree = parse(tokenize("(aset s 1)"))
        translator.compile_expr(parse_tree)
