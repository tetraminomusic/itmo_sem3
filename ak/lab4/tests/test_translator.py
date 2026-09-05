# tests/test_translator.py
import sys
import os
import pytest

# Добавляем папку src в путь поиска
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from parser import tokenize, parse, StringLiteral
from isa import Opcode
import translator


@pytest.fixture(autouse=True)
def reset_translator():
    """Сброс состояния перед каждым тестом."""
    translator.program = []
    translator.symbol_table = {}
    translator.data_memory = {}
    translator.functions = {}
    translator.local_vars = {}
    translator.current_reg = 1
    translator.label_counter = 0
    translator.data_address_counter = 100

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
    assert res_reg == "R1"  # Благодаря освобождению регистров всё должно свернуться в R1

def test_all_bitwise_and_shift_operations():
    """Проверка генерации всех битовых и сдвиговых инструкций."""
    code = """
    (progn
        (setq a (and 1 2))
        (setq b (or 3 4))
        (setq c (xor 5 6))
        (setq d (not 7))
        (setq e (lsl 8 1))
        (setq f (lsr 9 1))
        (setq g (rol 10 1))
        (setq h (ror 11 1))
        (setq i (asr 12 1))
        (setq j (% 13 2))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    opcodes = {instr.opcode for instr in clean_code}
    expected_opcodes = {
        Opcode.AND, Opcode.OR, Opcode.XOR, Opcode.NOT,
        Opcode.LSL, Opcode.LSR, Opcode.ROL, Opcode.ROR,
        Opcode.ASR, Opcode.MOD
    }
    assert expected_opcodes.issubset(opcodes)

@pytest.mark.parametrize("op_sign, expected_jump", [
    ("=", Opcode.JNZ),
    ("!=", Opcode.JZ),
    ("<", Opcode.JGE),
    ("<=", Opcode.JG),
    (">", Opcode.JLE),
    (">=", Opcode.JL),
])
def test_all_comparison_operators(op_sign, expected_jump):
    """Каждый знак сравнения должен порождать строгую инвертированную команду перехода."""
    code = f"(if ({op_sign} 10 20) 1 0)"
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    jump_instrs = [instr for instr in clean_code if instr.opcode == expected_jump]
    assert len(jump_instrs) == 1, f"Для оператора '{op_sign}' ожидался прыжок {expected_jump.name}"


def test_setq_non_string_variable_error():
    """Ошибка: имя переменной не является строкой (например, число)."""
    code = "(setq 123 456)"
    with pytest.raises(TypeError, match="Имя переменной должно быть строкой"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_setq_wrong_argument_count():
    """Ошибка: у setq не 2 аргумента."""
    code = "(setq x 1 2)"
    with pytest.raises(SyntaxError, match="Команда 'setq' требует ровно 2 аргумента"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_if_wrong_argument_count():
    """Ошибка: у if нет ветки else."""
    code = "(if (= 1 1) 10)"
    with pytest.raises(SyntaxError, match="'if' требует ровно 3 аргумента"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_undefined_variable_error():
    """Ошибка: чтение переменной, которую не объявляли через setq или defun."""
    code = "(+ unknown_var 10)"
    with pytest.raises(NameError, match="Использование необъявленной переменной"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_unknown_operation_error():
    """Ошибка: вызов несуществующей функции или операции."""
    code = "(foobar 1 2)"
    with pytest.raises(SyntaxError, match="Неизвестная операция или необъявленная функция"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_binary_op_wrong_arity():
    """Ошибка: сложение с 3 аргументами вместо 2."""
    code = "(+ 1 2 3)"
    with pytest.raises(SyntaxError, match="требует ровно 2 операнда"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_duplicate_function_arguments():
    """Ошибка: одинаковые имена параметров функции (defun foo (x x) ...)."""
    code = "(defun foo (x x) (+ x x))"
    with pytest.raises(SyntaxError, match="аргументы имеют одинаковые имена"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_full_pipeline_compilation_with_files(tmp_path):
    """Проверка записи бинарного файла и текстового листинга через compile_file."""
    source_file = tmp_path / "prog.lisp"
    target_file = tmp_path / "prog.bin"
    listing_file = tmp_path / "prog.txt"

    # Создаем временный файл с кодом
    source_file.write_text("""
    (progn
        (setq s "Test")
        (out 1 65)
    )
    """, encoding="utf-8")

    # Запускаем компиляцию
    translator.compile_file(str(source_file), str(target_file), str(listing_file))

    # Проверяем, что бинарник создался и не пустой
    assert target_file.exists()
    assert target_file.stat().st_size > 0

    # Проверяем, что листинг создался и содержит нужные подстроки
    assert listing_file.exists()
    listing_content = listing_file.read_text(encoding="utf-8")
    assert "OUT 1, R" in listing_content
    assert "HLT" in listing_content


def test_recursive_function_compilation():
    """Рекурсивная функция (самовызов) должна корректно генерировать CALL на саму себя."""
    code = """
    (progn
        (defun countdown (n)
            (if (<= n 0)
                0
                (countdown (- n 1))))
        (countdown 5)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Проверяем, что есть как минимум 2 вызова CALL (один внутри рекурсии, один снаружи)
    calls = [instr for instr in clean_code if instr.opcode == Opcode.CALL]
    assert len(calls) == 2


def test_function_calling_another_function():
    """Функция A вызывает функцию B."""
    code = """
    (progn
        (defun double (x) (* x 2))
        (defun quad (x) (double (double x)))
        (setq res (quad 3))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Должны быть зарегистрированы обе функции
    assert "double" in translator.functions
    assert "quad" in translator.functions
    assert len([instr for instr in clean_code if instr.opcode == Opcode.CALL]) == 3


def test_variable_shadowing():
    """Локальный аргумент функции должен затенять глобальную переменную с тем же именем."""
    code = """
    (progn
        (setq x 100)           ; Глобальная x
        (defun foo (x) (+ x 1)) ; Локальный аргумент x затеняет глобальную
        (foo 5)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Внутри тела функции обращение к x должно быть через сложение регистров (ADD R..., R1, R0),
    # а НЕ через чтение из памяти (LD R..., R..., 0)!
    inside_foo_code = clean_code[4:7]
    opcodes_inside_foo = [instr.opcode for instr in inside_foo_code]
    assert Opcode.LD not in opcodes_inside_foo


def test_complex_expressions_as_call_arguments():
    """Вызов функции со сложными математическими выражениями в аргументах."""
    code = """
    (progn
        (defun sum3 (a b c) (+ (+ a b) c))
        (sum3 (+ 1 2) (* 3 4) (- 10 5))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Должна успешно скомпилироваться без исчерпания регистров
    assert clean_code[-1].opcode == Opcode.HLT


def test_multiple_pascal_strings_allocation():
    """Несколько строк должны укладываться в памяти строго друг за другом без наложений."""
    code = """
    (progn
        (setq s1 "ABC")   ; длина 3 -> ячейки 101, 102..104
        (setq s2 "WXYZ")  ; длина 4 -> ячейки 106, 107..110
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)

    # Проверяем адреса первой строки
    addr_s1 = 101
    assert translator.data_memory[addr_s1] == 3
    assert translator.data_memory[addr_s1 + 1] == ord('A')

    # Проверяем адреса второй строки (должна лежать строго после первой переменной и строки)
    addr_s2 = 106
    assert translator.data_memory[addr_s2] == 4
    assert translator.data_memory[addr_s2 + 1] == ord('W')


def test_double_negation_not():
    """Двойное отрицание (not (not x))."""
    code = "(not (not 1))"
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    not_ops = [instr for instr in clean_code if instr.opcode == Opcode.NOT]
    assert len(not_ops) == 2


def test_nested_progn():
    """Вложенные блоки progn внутри других progn."""
    code = """
    (progn
        (progn
            (setq a 1)
            (setq b 2))
        (+ a b)
    )
    """
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert clean_code[-1].opcode == Opcode.HLT


def test_function_called_before_declaration():
    """Ошибка: вызов функции до того, как компилятор встретил её defun."""
    code = """
    (progn
        (foo 5)
        (defun foo (x) x)
    )
    """
    with pytest.raises(SyntaxError, match="Неизвестная операция или необъявленная функция"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_empty_parentheses_error():
    """Ошибка: пустые скобки '()' не являются валидным выражением."""
    code = "()"
    with pytest.raises(SyntaxError):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_collatz_algorithm_compilation():
    """Скомпилировать настоящий рекурсивный алгоритм Коллатца из твоего варианта!"""
    code = """
    (progn
        (defun collatz (n count)
            (if (= n 1)
                count
                (if (= (% n 2) 0)
                    (collatz (/ n 2) (+ count 1))
                    (collatz (+ (* 3 n) 1) (+ count 1)))))

        (setq steps (collatz 13 0))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Проверяем, что есть деление с остатком %, обычное деление /, умножение *, и вызовы CALL
    opcodes = {instr.opcode for instr in clean_code}
    assert Opcode.MOD in opcodes
    assert Opcode.DIV in opcodes
    assert Opcode.MUL in opcodes
    assert Opcode.CALL in opcodes


def test_zero_argument_function():
    """Функция без аргументов (defun get_constant () 42)."""
    code = """
    (progn
        (defun get_magic () 42)
        (setq res (get_magic))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert translator.functions["get_magic"] == 0
    assert Opcode.CALL in [instr.opcode for instr in clean_code]


def test_nested_ifs_in_both_branches():
    """Сложное дерево: if внутри then и if внутри else."""
    code = """
    (if (> x 10)
        (if (> x 20) 1 2)
        (if (< x 5) 3 4))
    """
    # Регистрируем переменную x
    translator.symbol_table["x"] = 100
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Должно быть 3 инструкции CMP для трех условий
    cmps = [instr for instr in clean_code if instr.opcode == Opcode.CMP]
    assert len(cmps) == 3


def test_complex_expressions_in_if_condition():
    """Сложные формулы внутри условия сравнения: (= (+ 1 2) (* 3 1))."""
    code = "(if (= (+ 1 2) (* 3 1)) 10 20)"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert Opcode.CMP in [instr.opcode for instr in clean_code]


def test_variable_reassignment_reuses_memory():
    """Переприсваивание переменной обязано переиспользовать тот же адрес памяти!"""
    code = """
    (progn
        (setq a 10)
        (setq a 20)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)

    # Адрес для переменной 'a' должен остаться равен 100, а счетчик не должен улететь вперед
    assert translator.symbol_table["a"] == 100
    assert translator.data_address_counter == 101


def test_complex_string_with_punctuation():
    """Строка с пробелами, знаками препинания и цифрами."""
    code = '(setq msg "Hello, World! 123")'
    ast = parse(tokenize(code))
    translator.compile_expr(ast)

    str_addr = 101
    assert translator.data_memory[str_addr] == len("Hello, World! 123")
    assert translator.data_memory[str_addr + 1] == ord('H')
    assert translator.data_memory[str_addr + 7] == ord(' ')
    assert translator.data_memory[str_addr + 8] == ord('W')


def test_single_item_progn():
    """Блок progn, содержащий только одно выражение."""
    code = "(progn 42)"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    assert res_reg == "R1"


def test_defun_missing_body_error():
    """Ошибка: забыли тело функции (defun foo (x))."""
    code = "(defun foo (x))"
    with pytest.raises(SyntaxError, match="требует:"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_defun_non_list_arguments_error():
    """Ошибка: аргументы переданы не в виде списка (defun foo x (+ x 1))."""
    code = "(defun foo x (+ x 1))"
    with pytest.raises(TypeError, match="должен быть списком"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_out_missing_arguments():
    """Ошибка: у out не хватает значения."""
    code = "(out 1)"
    with pytest.raises(SyntaxError, match="требует два аргумента"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_in_extra_arguments():
    """Ошибка: у in лишний аргумент."""
    code = "(in 0 1)"
    with pytest.raises(SyntaxError, match="требует 1 аргумент"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_gcd_euclidean_algorithm():
    """Рекурсивный алгоритм Евклида для нахождения НОД двух чисел."""
    code = """
    (progn
        (defun gcd (a b)
            (if (= b 0)
                a
                (gcd b (% a b))))
        (setq res (gcd 48 18))
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert Opcode.MOD in [instr.opcode for instr in clean_code]
    assert Opcode.CALL in [instr.opcode for instr in clean_code]


def test_infix_to_rpn_precedence_function():
    """Функция определения приоритета операций для алгоритма infix_to_rpn."""
    code = """
    (defun get_precedence (op)
        (if (= op 43) 1          ; ASCII 43 это '+'
            (if (= op 42) 2      ; ASCII 42 это '*'
                0)))
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    cmps = [instr for instr in clean_code if instr.opcode == Opcode.CMP]
    assert len(cmps) == 2


def test_chained_if_else_ladder():
    """Длинная лестница из 5 вложенных if-else."""
    code = """
    (if (= x 1) 10
        (if (= x 2) 20
            (if (= x 3) 30
                (if (= x 4) 40 50))))
    """
    translator.symbol_table["x"] = 100
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    # Должно сгенерироваться 4 команды CMP и 4 команды перехода
    assert len([instr for instr in clean_code if instr.opcode == Opcode.CMP]) == 4


def test_progn_register_cleanup_many_statements():
    """Проверка, что в длинном progn регистры своевременно освобождаются и не утекают."""
    code = """
    (progn
        (+ 1 1)
        (+ 2 2)
        (+ 3 3)
        (+ 4 4)
        (+ 5 5)
        (+ 6 6)
        (+ 7 7)
        (+ 8 8)
        (+ 9 9)
        100
    )
    """
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    # Счетчик регистров не должен улететь в потолок
    assert translator.current_reg <= 3
    assert res_reg == "R1"


def test_function_modifying_global_variable():
    """Функция внутри себя меняет глобальную переменную через setq (Side Effect)."""
    code = """
    (progn
        (setq counter 0)
        (defun increment_global ()
            (setq counter (+ counter 1)))
        (increment_global)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    # Должны присутствовать инструкции записи в память ST
    assert Opcode.ST in [instr.opcode for instr in clean_code]


def test_five_argument_function():
    """Функция с 5 аргументами (раскладка по R1, R2, R3, R4, R5)."""
    code = """
    (progn
        (defun sum5 (a b c d e)
            (+ a (+ b (+ c (+ d e)))))
        (sum5 1 2 3 4 5)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert translator.functions["sum5"] == 5


def test_zero_literal_in_math_and_cmp():
    """Корректная обработка нуля (0) в константах и сравнениях."""
    code = "(if (= 0 0) (+ 0 0) (- 0 0))"
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert clean_code[-1].opcode == Opcode.HLT


def test_combined_shifts_and_rotations():
    """Сложная цепочка сдвигов и ротаций в одном выражении."""
    code = "(rol (ror (lsl (lsr 100 1) 1) 2) 2)"
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    opcodes = {instr.opcode for instr in clean_code}
    assert {Opcode.LSL, Opcode.LSR, Opcode.ROL, Opcode.ROR}.issubset(opcodes)


def test_calling_variable_as_function_error():
    """Ошибка: попытка вызвать переменную как функцию."""
    code = """
    (progn
        (setq x 10)
        (x 5)
    )
    """
    with pytest.raises(SyntaxError, match="Неизвестная операция или необъявленная функция"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_setq_list_as_variable_name_error():
    """Ошибка: попытка передать список вместо имени переменной в setq."""
    code = "(setq (a b) 10)"
    with pytest.raises(TypeError, match="Имя переменной должно быть строкой"):
        ast = parse(tokenize(code))
        translator.compile_expr(ast)


def test_parentheses_inside_string_literal():
    """Круглые скобки внутри строки в кавычках НЕ должны ломать дерево AST."""
    code = '(setq parens "((hello (world)))")'
    ast = parse(tokenize(code))
    translator.compile_expr(ast)

    # Проверяем, что строка осталась цельной внутри памяти данных
    str_addr = 101
    expected_text = "((hello (world)))"
    assert translator.data_memory[str_addr] == len(expected_text)
    assert translator.data_memory[str_addr + 1] == ord('(')
    assert translator.data_memory[str_addr + 2] == ord('(')


def test_setq_as_expression_inside_math():
    """Проверка требования методички: setq возвращает значение и работает внутри формул!"""
    code = "(+ (setq a 5) 10)"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    # Должна быть и запись в память переменной 'a', и сложение ADD
    assert translator.symbol_table["a"] == 100
    assert Opcode.ST in [instr.opcode for instr in clean_code]
    assert Opcode.ADD in [instr.opcode for instr in clean_code]


def test_setq_inside_if_condition():
    """Присваивание прямо внутри проверки условия: (if (= (setq x 5) 5) 100 200)."""
    code = "(if (= (setq x 5) 5) 100 200)"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)

    assert translator.symbol_table["x"] == 100
    assert Opcode.CMP in [instr.opcode for instr in clean_code]


def test_comments_interleaved_inside_expression():
    """Комментарии, вставленные прямо между аргументами на разных строках."""
    code = """
    (+ 
        10 ; первый аргумент
        20 ; второй аргумент
    )
    """
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert Opcode.ADD in [instr.opcode for instr in clean_code]


def test_weird_whitespace_and_tabs():
    """Код с дикой смесью табуляций, пустых строк и пробелов."""
    code = "\n\n\t  (progn \t\t\n   (+   5 \t 10  ) \n  ) \t\n"
    ast = parse(tokenize(code))
    res_reg = translator.compile_expr(ast)
    assert res_reg == "R1"


def test_forwarding_function():
    # Функция, просто возвращающая вызов другой функции.
    code = """
    (progn
        (defun inc (x) (+ x 1))
        (defun proxy (x) (inc x))
        (proxy 10)
    )
    """
    ast = parse(tokenize(code))
    translator.compile_expr(ast)
    clean_code = translator.link_program(translator.program)
    assert len([i for i in clean_code if i.opcode == Opcode.CALL]) == 2