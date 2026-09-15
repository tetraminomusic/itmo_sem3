import argparse
import struct
import sys

from isa import Instruction, Opcode
from parser import StringLiteral, parse, tokenize

current_reg = 1
label_counter = 0
data_address_counter = 1000

available_ports = [0, 1]

interrupt_handler = None

symbol_table: dict[str, int] = {}
data_memory: dict[int, int] = {}
functions: dict[str, int] = {}  # {"add_two", "Collatz"} - таблица зарегистрированных функций
local_vars: dict[str, str] = {}  # {"x": "R1", "y": "R2"...} - текущие локальные переменные

program: list[Instruction | str] = []

INVERSE_JUMPS = {
    "=": Opcode.JNZ,
    "!=": Opcode.JZ,
    "<": Opcode.JGE,
    ">=": Opcode.JL,
}

BINARY_OPS = {
    "+",
    "-",
    "*",
    "/",
    "%",
    "and",
    "or",
    "xor",
    "lsl",
    "lsr",
    "<<",
    ">>",
    "asl",
    "asr",
    "rol",
    "ror",
}

RESERVED_KEYWORDS = {
    "if",
    "defun",
    "setq",
    "progn",
    "+",
    "-",
    "*",
    "/",
    "%",
    "=",
    "!=",
    "<",
    "<=",
    ">",
    ">=",
    "in",
    "out",
    "and",
    "or",
    "xor",
    "not",
    "lsl",
    "lsr",
    "<<",
    ">>",
    "inc",
    "dec",
    "print",
    "aref",
    "aset",
    "definterrupt",
}

# Предварительный проход


def collect_function_signatures(node):
    if isinstance(node, list) and len(node) > 0:
        if node[0] == "defun" and len(node) == 4 and isinstance(node[2], list):
            func_name = node[1]
            arg_list = node[2]

            if func_name in RESERVED_KEYWORDS:
                raise SyntaxError(
                    f"Ошибка семантики: Нельзя назвать функцию зарезервированным словом '{func_name}'"
                )

            if func_name in functions:
                raise ValueError(
                    f"Ошибка семантики: Функция с именем '{func_name}' уже объявлена ранее"
                )

            functions[func_name] = len(arg_list)

        for sub in node:
            collect_function_signatures(sub)


# Размещает Pascal строку в памяти данных и возвращает её начальный адрес


def allocate_pstr(text: str) -> int:
    global data_address_counter
    start_addr = data_address_counter

    data_memory[start_addr] = len(text)
    data_address_counter += 1

    for char in text:
        data_memory[data_address_counter] = ord(char)
        data_address_counter += 1

    return start_addr


# Возвращает адрес существующей переменной или выделяет новый адрес в памяти


def get_or_allocate_var(var_name: str) -> int:
    global data_address_counter
    if var_name not in symbol_table:
        symbol_table[var_name] = data_address_counter
        data_address_counter += 1
    return symbol_table[var_name]


# Выдает имя следующего свободного регистра, который мы можем использовать для рекурсивного кода


def allocate_reg() -> str:
    global current_reg

    if current_reg > 10:
        raise RuntimeError("Ошибка компилятора: закончились свободные регистры")

    reg_name = f"R{current_reg}"
    current_reg += 1
    return reg_name


# Освобождает последний занятый регистр


def free_reg():
    global current_reg
    current_reg -= 1


# Компоновщик, нужный для замены символических меток на числовые адреса памяти


def link_program(raw_program: list) -> list:

    # Сначала разбираемся с таблицей векторов прерывания

    vector_table = [
        Instruction(Opcode.JMP, ["_start"]),
        Instruction(Opcode.JMP, [interrupt_handler])
        if interrupt_handler
        else Instruction(Opcode.IRET),
    ]

    full_program = vector_table + ["_start:"] + raw_program

    # Первый проход: находим адреса всех меток и собираем чистый список команд

    labels_map = {}
    clean_instructions = []
    current_address = 0

    for item in full_program:
        if isinstance(item, str) and item.endswith(":"):
            label_name = item[:-1]
            labels_map[label_name] = current_address
        else:
            clean_instructions.append(item)
            current_address += 1

    # Второй проход: подставляем числовые адреса вместо текстовых

    for instr in clean_instructions:
        for i, arg in enumerate(instr.args):
            if isinstance(arg, str) and arg in labels_map:
                instr.args[i] = labels_map[arg]

    clean_instructions.append(Instruction(Opcode.HLT))

    return clean_instructions


# Создаёт уникальную метку, используется для условий и преобразования с командами ветвления


def make_label(prefix: str = "L") -> str:
    global label_counter
    name = f"{prefix}_{label_counter}"
    label_counter += 1
    return name


# Компилирует нужное условие сравнения под знак сравнения + генерирует команду CMP и возвращает опкод прыжка в ELSE


def compile_condition(condition_node: list) -> Opcode:

    if (
        isinstance(condition_node, list)
        and len(condition_node) == 3
        and condition_node[0] in ("=", "!=", "<", "<=", ">", ">=")
    ):
        op = condition_node[0]
        left = condition_node[1]
        right = condition_node[2]

        if op == ">":
            reg_right = compile_expr(right)
            reg_left = compile_expr(left)
            program.append(Instruction(Opcode.CMP, [reg_right, reg_left]))
            free_reg()
            free_reg()
            return Opcode.JGE

        elif op == "<=":
            reg_right = compile_expr(right)
            reg_left = compile_expr(left)
            program.append(Instruction(Opcode.CMP, [reg_right, reg_left]))
            free_reg()
            free_reg()
            return Opcode.JL

        reg_left = compile_expr(left)
        reg_right = compile_expr(right)
        program.append(Instruction(Opcode.CMP, [reg_left, reg_right]))
        free_reg()
        free_reg()
        return INVERSE_JUMPS[op]

    cond_reg = compile_expr(condition_node)
    program.append(Instruction(Opcode.CMP, [cond_reg, "R0"]))
    free_reg()
    return Opcode.JZ


def compile_expr(node) -> str | None:
    global local_vars, current_reg, interrupt_handler

    # Проверяем, может это простое число

    if isinstance(node, int):
        reg = allocate_reg()
        program.append(Instruction(Opcode.LDI, [reg, node]))
        return reg

    # Проверяем строковую переменную

    if isinstance(node, str):
        if node in local_vars:
            reg = allocate_reg()
            program.append(Instruction(Opcode.ADD, [reg, local_vars[node], "R0"]))
            return reg

        if node in symbol_table:
            addr = symbol_table[node]
            reg = allocate_reg()
            program.append(Instruction(Opcode.LDI, [reg, addr]))
            program.append(Instruction(Opcode.LD, [reg, reg, 0]))
            return reg

        raise NameError(f"Использование необъявленной переменной: '{node}'")

    # Проверяем строковый литерал

    if isinstance(node, StringLiteral):
        str_addr = allocate_pstr(node.text)
        reg = allocate_reg()
        program.append(Instruction(Opcode.LDI, [reg, str_addr]))
        return reg

    # Рекурсивный случай: списковое выражение

    if isinstance(node, list):
        if len(node) == 0:
            raise SyntaxError("Пустые скобки '()' не являются допустимым выражением")

        op = node[0]

        # Разрешение прерывания

        if op == "ei":
            program.append(Instruction(Opcode.EI))
            return None

        # Запрет прерывания

        if op == "di":
            program.append(Instruction(Opcode.DI))
            return None

        # Чтение элемента массива по индексу

        if op == "aref":
            if len(node) != 3:
                raise SyntaxError(
                    "Команда 'aref' требует 2 аргумента: (aref массив индекс)"
                )

            base_expr = node[1]
            idx_expr = node[2]

            base_reg = compile_expr(base_expr)
            idx_reg = compile_expr(idx_expr)

            program.append(Instruction(Opcode.ADD, [base_reg, base_reg, idx_reg]))
            free_reg()

            program.append(Instruction(Opcode.LD, [base_reg, base_reg, 0]))
            return base_reg

        # Запись в массив/строку по индексу

        if op == "aset":
            if len(node) != 4:
                raise SyntaxError(
                    "Команда 'aset' требует 3 аргумента: (aset массив индекс значение)"
                )

            base_expr = node[1]
            idx_expr = node[2]
            val_expr = node[3]

            base_reg = compile_expr(base_expr)
            idx_reg = compile_expr(idx_expr)
            val_reg = compile_expr(val_expr)

            program.append(Instruction(Opcode.ADD, [base_reg, base_reg, idx_reg]))
            program.append(Instruction(Opcode.ST, [val_reg, base_reg, 0]))

            program.append(Instruction(Opcode.ADD, [base_reg, val_reg, "R0"]))

            free_reg()
            free_reg()
            return base_reg

        # Последовательное выполнение progn

        if op == "progn":
            last_reg = None
            for expr in node[1:]:
                if last_reg is not None:
                    free_reg()
                last_reg = compile_expr(expr)
            return last_reg

        # Объявление обработчика прерывания

        if op == "definterrupt":
            if len(node) != 4:
                raise SyntaxError(
                    "Конструкция 'definterrupt' требует: (definterrupt имя () тело)"
                )

            handler_name = node[1]
            body_expr = node[3]

            interrupt_handler = handler_name

            label_skip = make_label(f"skip_intr_{handler_name}")
            program.append(Instruction(Opcode.JMP, [label_skip]))
            program.append(f"{handler_name}:")

            for i in range(1, 11):
                program.append(Instruction(Opcode.PUSH, [f"R{i}"]))

            old_reg = current_reg
            current_reg = 1
            intr_res = compile_expr(body_expr)
            if intr_res is not None:
                free_reg()
            current_reg = old_reg

            for i in range(10, 0, -1):
                program.append(Instruction(Opcode.POP, [f"R{i}"]))

            program.append(Instruction(Opcode.IRET))
            program.append(f"{label_skip}:")
            return None

        # Объявление функции

        if op == "defun":
            if len(node) != 4:
                raise SyntaxError(
                    "Контрукция 'defun' требует: (defun имя (аргументы) тело)"
                )

            func_name = node[1]
            arg_list = node[2]
            body_expr = node[3]

            if not isinstance(arg_list, list):
                raise TypeError(
                    "Список аргументов функции должен быть списком в скобках ()"
                )

            if len(arg_list) != len(set(arg_list)):
                raise SyntaxError(
                    f"Ошибка в функции '{func_name}': аргументы имеют одинаковые имена"
                )

            label_after_func = make_label(f"skip_{func_name}")
            program.append(Instruction(Opcode.JMP, [label_after_func]))
            program.append(f"{func_name}:")

            old_locals = local_vars.copy()
            old_reg = current_reg

            local_vars = {arg_name: f"R{i + 1}" for i, arg_name in enumerate(arg_list)}
            current_reg = len(arg_list) + 1

            result_reg = compile_expr(body_expr)

            if result_reg != "R1" and result_reg is not None:
                program.append(Instruction(Opcode.ADD, ["R1", result_reg, "R0"]))

            program.append(Instruction(Opcode.RET))

            if result_reg is not None:
                free_reg()

            local_vars = old_locals
            current_reg = old_reg
            program.append(f"{label_after_func}:")
            return None

        # Печать

        if op == "print":
            if len(node) != 2:
                raise SyntaxError(
                    "Команда 'print' требует 1 аргумент: (print значение)"
                )
            val_reg = compile_expr(node[1])
            program.append(Instruction(Opcode.OUT, [1, val_reg]))
            return val_reg

        # Присваивание setq

        if op == "setq":
            if len(node) != 3:
                raise SyntaxError(
                    "Команда 'setq' требует ровно 2 аргумента: (setq имя значение)"
                )

            var_name = node[1]
            value_expr = node[2]

            if not isinstance(var_name, str):
                raise TypeError(
                    f"Имя переменной должно быть строкой, получено: {var_name}"
                )

            if var_name in RESERVED_KEYWORDS:
                raise SyntaxError(
                    f"Нельзя использовать зарезервированное слово '{var_name}' в качестве имени переменной"
                )

            addr = get_or_allocate_var(var_name)
            val_reg = compile_expr(value_expr)

            addr_reg = allocate_reg()
            program.append(Instruction(Opcode.LDI, [addr_reg, addr]))
            program.append(Instruction(Opcode.ST, [val_reg, addr_reg, 0]))
            free_reg()

            return val_reg

        # Ветвление if

        if op == "if":
            if len(node) != 4:
                raise SyntaxError(
                    "'if' требует ровно 3 аргумента: (if условие then else)"
                )

            condition = node[1]
            then_branch = node[2]
            else_branch = node[3]

            label_else = make_label("else")
            label_end = make_label("end")

            jump_to_else_op = compile_condition(condition)
            result_reg = allocate_reg()

            program.append(Instruction(jump_to_else_op, [label_else]))

            # THEN
            then_reg = compile_expr(then_branch)
            if then_reg is not None:
                program.append(Instruction(Opcode.ADD, [result_reg, then_reg, "R0"]))
                free_reg()
            program.append(Instruction(Opcode.JMP, [label_end]))

            # ELSE
            program.append(f"{label_else}:")
            else_reg = compile_expr(else_branch)
            if else_reg is not None:
                program.append(Instruction(Opcode.ADD, [result_reg, else_reg, "R0"]))
                free_reg()

            # END
            program.append(f"{label_end}:")
            return result_reg

        # Вызов пользовательской функции

        if op in functions:
            passed_args = node[1:]
            except_args_count = functions[op]

            if len(passed_args) != except_args_count:
                raise TypeError(
                    f"Ошибка вызова: функция '{op}' ожидает {except_args_count},"
                    f"но было передано {len(passed_args)}"
                )

            active_regs = [f"R{i}" for i in range(1, current_reg)]
            for r in active_regs:
                program.append(Instruction(Opcode.PUSH, [r]))

            arg_temp_regs = []
            for arg_expr in passed_args:
                arg_temp_regs.append(compile_expr(arg_expr))

            for i, temp_r in enumerate(arg_temp_regs):
                target_r = f"R{i + 1}"
                if temp_r != target_r:
                    program.append(Instruction(Opcode.ADD, [target_r, temp_r, "R0"]))

            program.append(Instruction(Opcode.CALL, [op]))

            for _ in arg_temp_regs:
                free_reg()

            res_reg = allocate_reg()
            program.append(Instruction(Opcode.ADD, [res_reg, "R1", "R0"]))

            for r in reversed(active_regs):
                program.append(Instruction(Opcode.POP, [r]))

            return res_reg

        # Вывод в порт

        if op == "out":
            if len(node) != 3:
                raise SyntaxError(
                    "Команда 'out' требует два аргумента: (out порт значение)"
                )

            port_num = node[1]
            val_expr = node[2]

            if not isinstance(port_num, int) or port_num not in available_ports:
                raise ValueError(f"Некорректный номер порта: {port_num}")

            val_reg = compile_expr(val_expr)
            program.append(Instruction(Opcode.OUT, [port_num, val_reg]))
            free_reg()
            return None

        # Ввод из порта

        if op == "in":
            if len(node) != 2:
                raise SyntaxError("Команда 'in' требует 1 аргумент: (in порт)")

            port_num = node[1]
            if not isinstance(port_num, int) or port_num not in available_ports:
                raise ValueError(f"Некорректный номер порта: {port_num}")

            reg = allocate_reg()
            program.append(Instruction(Opcode.IN, [reg, port_num]))
            return reg

        # Унарные операции

        if op == "not":
            arg_reg = compile_expr(node[1])
            program.append(Instruction(Opcode.NOT, [arg_reg, arg_reg]))
            return arg_reg

        if op == "inc":
            arg_reg = compile_expr(node[1])
            program.append(Instruction(Opcode.INC, [arg_reg]))
            return arg_reg

        if op == "dec":
            arg_reg = compile_expr(node[1])
            program.append(Instruction(Opcode.DEC, [arg_reg]))
            return arg_reg

        # Арифметика вариативная (+ 1 2 3...)

        if op in ("+", "*"):
            if len(node) < 3:
                raise SyntaxError(f"Операция '{op}' требует как минимум 2 операнда")

            accum_reg = compile_expr(node[1])
            for next_expr in node[2:]:
                next_reg = compile_expr(next_expr)
                if op == "+":
                    program.append(
                        Instruction(Opcode.ADD, [accum_reg, accum_reg, next_reg])
                    )
                elif op == "*":
                    program.append(
                        Instruction(Opcode.MUL, [accum_reg, accum_reg, next_reg])
                    )
                free_reg()

            return accum_reg

        # Бинарная арифметика и побитовые операции

        if op in BINARY_OPS:
            if len(node) != 3:
                raise SyntaxError(
                    f"Операция '{op}' требует ровно 2 операнда, получено: {len(node) - 1}"
                )

            left = node[1]
            right = node[2]

            left_reg = compile_expr(left)
            right_reg = compile_expr(right)

            if op == "-":
                program.append(Instruction(Opcode.SUB, [left_reg, left_reg, right_reg]))
            elif op == "/":
                program.append(Instruction(Opcode.DIV, [left_reg, left_reg, right_reg]))
            elif op == "%":
                program.append(Instruction(Opcode.MOD, [left_reg, left_reg, right_reg]))
            elif op == "and":
                program.append(Instruction(Opcode.AND, [left_reg, left_reg, right_reg]))
            elif op == "or":
                program.append(Instruction(Opcode.OR, [left_reg, left_reg, right_reg]))
            elif op == "xor":
                program.append(Instruction(Opcode.XOR, [left_reg, left_reg, right_reg]))
            elif op in ("lsl", "<<", "asr", "rol"):
                program.append(Instruction(Opcode.LSL, [left_reg, left_reg, right_reg]))
            elif op in ("lsr", ">>", "asr", "ror"):
                program.append(Instruction(Opcode.LSR, [left_reg, left_reg, right_reg]))

            free_reg()
            return left_reg

        raise SyntaxError(f"Неизвестная операция или необъявленная функция: '{op}'")
    return None


def generate_listing(instructions: list) -> str:
    lines = []
    for addr, instr in enumerate(instructions):
        if isinstance(instr, Instruction):
            hex_code = f"0x{instr.encode():08X}"
            lines.append(f"{addr:04d} - {hex_code} - {instr}")
        elif isinstance(instr, int):
            hex_code = f"0x{instr:08X}"
            lines.append(f"{addr:04d} - {hex_code} - VECTOR_DATA 0x{instr:04X}")
    return "\n".join(lines)


def compile_file(source_file: str, target_file: str, listing_file: str | None = None):
    global program, symbol_table, data_memory, functions, local_vars
    global current_reg, label_counter, data_address_counter, interrupt_handler

    program = []
    symbol_table = {}
    data_memory = {}
    functions = {}
    local_vars = {}
    current_reg = 1
    label_counter = 0
    data_address_counter = 1000
    interrupt_handler = None

    with open(source_file, "r", encoding="utf-8") as f:
        code_text = f.read()

    tokens = tokenize(code_text)
    ast = parse(tokens)

    collect_function_signatures(ast)

    compile_expr(ast)

    machine_code = link_program(program)

    memory_dump = [0] * 4096

    for addr, instr in enumerate(machine_code):
        if isinstance(instr, Instruction):
            memory_dump[addr] = instr.encode()
        elif isinstance(instr, int):
            memory_dump[addr] = instr

    for addr, val in data_memory.items():
        memory_dump[addr] = val

    with open(target_file, "wb") as f:
        f.writelines(struct.pack(">I", word & 0xFFFF_FFFF) for word in memory_dump)

    print(f"Машинный код записан в: {target_file}")

    if listing_file:
        listing_text = generate_listing(machine_code)
        with open(listing_file, "w", encoding="utf-8") as f:
            f.write(listing_text)
        print(f"Отладочный листинг записан в: {listing_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Консольный транслятор LISP в машинный код RISC процессора"
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Путь к исходному файлу (.lisp)"
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Путь к выходному бинарному файлу (.bin)"
    )
    parser.add_argument(
        "-l",
        "--listing",
        default=None,
        help="Путь к файлу листинга (.txt, опционально)",
    )

    args = parser.parse_args()

    try:
        compile_file(args.input, args.output, args.listing)
    except Exception as e:
        print(f"Ошибка компиляции: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
