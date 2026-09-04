from isa import Opcode, Instruction
from parser import tokenize, parse, StringLiteral

current_reg = 1
label_counter = 0
data_address_counter = 100

symbol_table = {}
data_memory = {}

program = []

INVERSE_JUMPS = {
    '=':  Opcode.JNZ,
    '!=': Opcode.JZ,
    '<':  Opcode.JGE,
    '<=': Opcode.JG,
    '>':  Opcode.JLE,
    '>=': Opcode.JL,
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
    reg_name = f"R{current_reg}"
    current_reg += 1
    return reg_name


# Освобождает последний занятый регистр

def free_reg():
    global current_reg
    current_reg -= 1


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

    # Проверяем, может это вообще простое число   

    if isinstance(node, int):

        #   Запись простого числа в регистр - простое число 5
        #   Для этого используем команду LD с записью нашего конкретного числа

        reg = allocate_reg()
        program.append(Instruction(Opcode.LDI, [reg, node]))
        return reg

    # Проверяем, что это какая-то строковая переменная

    if isinstance(node, str):
        if node not in symbol_table:
            raise NameError(f"Использование необъявленной переменной: '{node}'")

        addr = symbol_table[node]
        reg = allocate_reg()

        # Грузим адрес в регистр

        program.append(Instruction(Opcode.LDI, [reg, addr]))
        program.append(Instruction(Opcode.LD, [reg, reg, 0]))
        return reg

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

        op = node[0]

        # Присваивание setq

        if op == 'setq':
            var_name = node[1]      # 'x'
            value_expr = node[2]    # Выражение справа, которое мы хотим записать

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
            program.append(Instruction(Opcode.ADD, [result_reg, then_reg, "R0"]))
            free_reg()
            program.append(Instruction(Opcode.JMP, [label_end]))

            #ELSE
            program.append(f"{label_else}:")    # пишем метку
            else_reg = compile_expr(else_branch)
            program.append(Instruction(Opcode.ADD, [result_reg, else_reg, "R0"]))
            free_reg()

            #END
            program.append(f"{label_end}:")
            return result_reg
                
        # Арифметика

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

        free_reg()
        return left_reg


    # 1. Присваиваем x = 10
# 2. Считаем x + 5
test_code = "(setq x 10)"
ast1 = parse(tokenize(test_code))
compile_expr(ast1)

test_code_2 = "(+ x 5)"
ast2 = parse(tokenize(test_code_2))
compile_expr(ast2)

print("Таблица символов (где лежат переменные):", symbol_table)
print("\nСгенерированный ассемблер:")
for instr in program:
    print(instr)
