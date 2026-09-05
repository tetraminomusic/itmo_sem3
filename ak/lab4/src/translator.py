import sys
import argparse
import pickle
from isa import Opcode, Instruction
from parser import tokenize, parse, StringLiteral

current_reg = 1
label_counter = 0
data_address_counter = 100

available_ports = [0, 1]

symbol_table = {}
data_memory = {}
functions = {}                  # {"add_two", "Collatz"} - таблица зарегистрированных функций
local_vars = {}                 # {"x": "R1", "y": "R2"...} - текущие локальные переменные

program = []

INVERSE_JUMPS = {
    '=':  Opcode.JNZ,
    '!=': Opcode.JZ,
    '<':  Opcode.JGE,
    '<=': Opcode.JG,
    '>':  Opcode.JLE,
    '>=': Opcode.JL,
}

BINARY_OPS = {
            '+', '-', '*', '/', '%', 
            'and', 'or', 'xor', 
            'lsl', 'lsr', 'asr', 'rol', 'ror', '<<', '>>'
}


RESERVED_KEYWORDS = {
    'if', 'defun', 'setq', 'progn', 
    '+', '-', '*', '/', '%', 
    '=', '!=', '<', '<=', '>', '>=',
    'in', 'out',
    'and', 'or', 'xor', 'not',
    'lsl', 'lsr', 'asr', 'rol', 'ror', '<<', '>>'
}

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
    global current_reg      # тип используем глобальную для файла переменную

    if current_reg > 10:
        raise RuntimeError("Ошибка компилятора: закончились свободные регистры")

    reg_name = f"R{current_reg}"
    current_reg += 1
    return reg_name


# Освобождает последний занятый регистр

def free_reg():
    global current_reg
    current_reg -= 1

# Компоновщик, нужный для замены символических метов на числовые адреса памяти

def link_program(raw_program: list) -> list:
    labels_map = {}
    clean_instructions = []

    # певрый проход: находим адреса всех метов и собираем чистый список команд
    current_address = 0

    for item in raw_program:
        if isinstance(item, str) and item.endswith(':'):
            label_name = item[:-1]
            labels_map[label_name] = current_address
        else:
            clean_instructions.append(item)
            current_address += 1

    # второй проход: подставляем числовые адреса заместо текстовых

    for instr in clean_instructions:
        for i, arg in enumerate(instr.args):

            # Если аргумент был названием какой нибудь метки, которую мы использовали

            if isinstance(arg, str) and arg in labels_map:
                instr.args[i] = labels_map[arg]

    # Кек, забыл добавить HLT

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
    op = condition_node[0]
    left = condition_node[1]
    right = condition_node[2]

    if op not in INVERSE_JUMPS:
        raise ValueError(f"Неизвестный оператор сравнения: {op}")

    reg_left = compile_expr(left)
    reg_right = compile_expr(right)

    program.append(Instruction(Opcode.CMP, [reg_left, reg_right]))

    free_reg()
    free_reg()

    return INVERSE_JUMPS[op]

def compile_expr(node) -> str:
    global local_vars

    # Проверяем, может это вообще простое число   

    if isinstance(node, int):

        #   Запись простого числа в регистр - простое число 5
        #   Для этого используем команду LD с записью нашего конкретного числа

        reg = allocate_reg()
        program.append(Instruction(Opcode.LDI, [reg, node]))
        return reg

    # Проверяем, что это какая-то строковая переменная

    if isinstance(node, str):

        # Локальные переменные

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

    # Проверяем, что это возможно какая-то строка

    if isinstance(node, StringLiteral):
        str_addr = allocate_pstr(node.text)

        # Загружаем адрес строки в регистр

        reg = allocate_reg()
        program.append(Instruction(Opcode.LDI, [reg, str_addr]))

        # Возвращаем регистр, где лежит указатель на строку

        return reg


    # Рекурсивный случай, если узел дерева - это операция в скобках

    if isinstance(node, list):

        if len(node) == 0:
            raise SyntaxError("Пустые скобки '()' не являются допустимым выражением")

        op = node[0]

        # Если это команда на последовательное выполнение progn

        if op == 'progn':
            last_reg = None
            for expr in node [1:]:
                if last_reg is not None:
                    free_reg()
                last_reg = compile_expr(expr)
            return last_reg

        # Если это команда создания новой функции

        if op == 'defun':

            if len(node) != 4:
                raise SyntaxError("Контрукция 'defun' требует: (defun имя (аргументы) тело)")

            func_name = node[1] # 'add_two'
            arg_list = node[2]  # ['x']
            body_expr = node[3] # ['+', 'x', 2]

            if not isinstance(arg_list, list):
                raise TypeError("Список аргументов функции должен быть списком в скобках ()")

            # Не объявлена ли функция с зарезервированным именем

            if func_name in RESERVED_KEYWORDS:
                raise SyntaxError(f"Ошибка семантики: Нельзя назвать функции зарезервированным словом '{func_name}'")

            # Не объявлена ли функция с таким именем уже

            if func_name in functions:
                raise ValueError(f"Ошибка семантики: Функция с именем '{func_name}' уже объявлена ранее")

            # Проверка на наличие дубликов среди аргументов 

            if len(arg_list) != len(set(arg_list)):
                raise SyntaxError(f"Ошибка в функции '{func_name}': аргументы имеют одинаковые имена")

            functions[func_name] = len(arg_list)

            label_after_func = make_label(f"skip_{func_name}")

            # Прыгаем в обход тела функции (дабы её случайно не выполнить)

            program.append(Instruction(Opcode.JMP, [label_after_func]))

            program.append(f"{func_name}:")

            # Закидываем адрес возврата в стек, дабы можно было адекватно реализовать рекурсию

            program.append(Instruction(Opcode.PUSH, ["LR"]))

            # Настраиваем аргументы (первый аргумент в R1, второй в R2 и так далее)

            old_locals = local_vars.copy()
            local_vars = {}
            for i, arg_name in enumerate(arg_list):
                local_vars[arg_name] = f"R{i+1}"

            result_reg = compile_expr(body_expr)

            if result_reg != "R1":
                program.append(Instruction(Opcode.ADD, ["R1", result_reg, "R0"]))

            program.append(Instruction(Opcode.POP, ["LR"]))
            program.append(Instruction(Opcode.RET))

            local_vars = old_locals

            program.append(f"{label_after_func}:")

            return None

        # Присваивание setq

        if op == 'setq':

            if len(node) != 3:
                raise SyntaxError("Команда 'setq' требует ровно 2 аргумента: (setq имя значение)")

            var_name = node[1]      # 'x'
            value_expr = node[2]    # Выражение справа, которое мы хотим записать

            if not isinstance(var_name, str):
                raise TypeError(f"Имя переменной должно быть строкой, получено: {var_name}")

            if var_name in RESERVED_KEYWORDS:
                raise SyntaxError(f"Нельзя использовать зарезервированное слово '{var_name}' в качестве имени переменной")

            

            addr = get_or_allocate_var(var_name)
            val_reg = compile_expr(value_expr)

            # Выделяем временный регистр под адрес ячейки
            addr_reg = allocate_reg()
            program.append(Instruction(Opcode.LDI, [addr_reg, addr]))

            # Сохраняем в память по нужному адресу
            program.append(Instruction(Opcode.ST, [val_reg, addr_reg, 0]))

            free_reg()

            return val_reg

        # Обработка If

        if op == 'if':

            if len(node) != 4:
                raise SyntaxError("'if' требует ровно 3 аргумента: (if условие then else)")

            condition = node[1]         # (= x 1) for exmp
            then_branch = node[2]
            else_branch = node[3]

            # Создаём уникальные метки для ветвлений

            label_else = make_label("else")
            label_end = make_label("end")

            # Вычисляем условие + ставим флаги NZVC

            jump_to_else_op = compile_condition(condition)

            # Выделяем один регистр для итогового результата всего if

            result_reg = allocate_reg()

            program.append(Instruction(jump_to_else_op, [label_else]))

            #THEN
            then_reg = compile_expr(then_branch)
            if then_reg is not None:
                program.append(Instruction(Opcode.ADD, [result_reg, then_reg, "R0"]))
                free_reg()
            program.append(Instruction(Opcode.JMP, [label_end]))

            #ELSE
            program.append(f"{label_else}:")    # пишем метку
            else_reg = compile_expr(else_branch)
            if else_reg is not None:
                program.append(Instruction(Opcode.ADD, [result_reg, else_reg, "R0"]))
                free_reg()


            #END
            program.append(f"{label_end}:")
            return result_reg

        # Если это пользовательская функция

        if op in functions:
            passed_args = node[1:]
            except_args_count = functions[op]

            if len(passed_args) != except_args_count:
                raise TypeError(
                    f"Ошибка вызова: функция '{op}' ожидает {except_args_count},"
                    f"но было передано {len(passed_args)}"
                )

            for i, arg_expr in enumerate(passed_args):
                target_reg = f"R{i+1}"
                res_reg = compile_expr(arg_expr)
                if res_reg != target_reg:
                    program.append(Instruction(Opcode.ADD, [target_reg, res_reg, "R0"]))

            program.append(Instruction(Opcode.CALL, [op]))

            out_reg = allocate_reg()
            program.append(Instruction(Opcode.ADD, [out_reg, "R1", "R0"]))
            return out_reg

        # Вывод в конкретный порт

        if op == 'out':

            if len(node) != 3:
                raise SyntaxError("Команда 'out' требует два аргумента: (out порт значение)")

            port_num = node[1]
            val_expr = node[2]

            if not isinstance(port_num, int) or port_num not in available_ports:
                raise ValueError(f"Некорректный номер порта: {port_num}")

            val_reg = compile_expr(val_expr)

            program.append(Instruction(Opcode.OUT, [port_num, val_reg]))

            free_reg()
            return None

        # Ввод в конкретный порт

        if op == 'in':
            if len(node) != 2:
                raise SyntaxError("Команда 'in' требует 1 аргумент: (in порт)")

            port_num = node[1]

            if not isinstance(port_num, int) or port_num not in available_ports:
                raise ValueError(f"Некорректный номер порта: {port_num}")

            # выделяем регистр под прочитанное значение

            reg = allocate_reg()

            program.append(Instruction(Opcode.IN, [reg, port_num]))

            return reg

        # Унарная операция логического NOT

        if op == 'not':
            arg_reg = compile_expr(node[1])
            program.append(Instruction(Opcode.NOT, [arg_reg, arg_reg]))
            return arg_reg

        # Арифметика

        if op in BINARY_OPS:
            if len(node) != 3:
                raise SyntaxError(f"Операция '{op}' требует ровно 2 операнда, получено: {len(node) - 1}")
            
            left = node[1]
            right = node[2]

            left_reg = compile_expr(left)
            right_reg = compile_expr(right)

            if op == '+':
                program.append(Instruction(Opcode.ADD, [left_reg, left_reg, right_reg]))
            elif op == '-':
                program.append(Instruction(Opcode.SUB, [left_reg, left_reg, right_reg]))
            elif op == '*':
                program.append(Instruction(Opcode.MUL, [left_reg, left_reg, right_reg]))
            elif op == '/':
                program.append(Instruction(Opcode.DIV, [left_reg, left_reg, right_reg]))
            elif op == '%':
                program.append(Instruction(Opcode.MOD, [left_reg, left_reg, right_reg]))

            # Побитовая логика

            elif op == 'and':
                program.append(Instruction(Opcode.AND, [left_reg, left_reg, right_reg]))
            elif op == 'or':
                program.append(Instruction(Opcode.OR, [left_reg, left_reg, right_reg]))
            elif op == 'xor':
                program.append(Instruction(Opcode.XOR, [left_reg, left_reg, right_reg]))

            # Слдвиги

            elif op in ('lsl', '<<'):
                program.append(Instruction(Opcode.LSL, [left_reg, left_reg, right_reg]))
            elif op in ('lsr', '>>'):
                program.append(Instruction(Opcode.LSR, [left_reg, left_reg, right_reg]))
            elif op == 'asr':
                program.append(Instruction(Opcode.ASR, [left_reg, left_reg, right_reg]))
            elif op == 'rol':
                program.append(Instruction(Opcode.ROL, [left_reg, left_reg, right_reg]))
            elif op == 'ror':
                program.append(Instruction(Opcode.ROR, [left_reg, left_reg, right_reg]))

            # Если не нашли нужную операцию

        else:
            raise SyntaxError(f"Неизвестная операция или необъявленная функция: '{op}'")

        free_reg()
        return left_reg



# Сохранение в файлы + cli интерфейс


# <address> - <HEXCODE> - <mnemonic>

def generate_listing(instructions: list) -> str:
    lines = []
    for addr, instr in enumerate(instructions):
        hex_code = f"0x{instr.encode():08X}"
        lines.append(f"{addr:04d} - {hex_code} - {instr}")
    return "\n".join(lines)

# читает исходный файл lisp, компилирует и сохраняет в выходной файл

def compile_file(source_file: str, target_file: str, listing_file: str = None):

    # Делаем программу реентерабельной

    global program, symbol_table, data_memory, functions, local_vars
    global current_reg, label_counter, data_address_counter
    program = []
    symbol_table = {}
    data_memory = {}
    functions = {}
    local_vars = {}
    current_reg = 1
    label_counter = 0
    data_address_counter = 100

    with open(source_file, "r", encoding="utf-8") as f:
        code_text = f.read()

    # токенизация + парсинг

    tokens = tokenize(code_text)
    ast = parse(tokens)

    # компиляция

    compile_expr(ast)

    # линковка

    machine_code = link_program(program)

    # Сохраняем в бинарник
    
    payload = {
        "code": machine_code,
        "data_memory": data_memory,
        "symbol_table": symbol_table
    }

    with open(target_file, "wb") as f:
        pickle.dump(payload, f)

    print(f"Машинный код записан в: {target_file}")

    # Сохраняем отладочный файл/листинг

    if listing_file:
        listing_text = generate_listing(machine_code)
        with open(listing_file, "w", encoding="utf-8") as f:
            f.write(listing_text)
        print(f"Отладочный листинг записан в: {listing_file}")


# Точка входа для работы из консоли

def main():
    parser = argparse.ArgumentParser(description="Консольный транслятор LISP в машинный код RISC процессора")
    parser.add_argument("-i", "--input", required=True, help="Путь к исходному файлу (.lisp)")
    parser.add_argument("-o","--output", required=True, help="Путь к выходному бинарному файлу (.bin)")
    parser.add_argument("-l", "--listing", default=None, help="Путь к файлу листинга (.txt, опционально)")

    args = parser.parse_args()

    try:
        compile_file(args.input, args.output, args.listing)
    except Exception as e:
        print(f"Ошибка компиляции: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

