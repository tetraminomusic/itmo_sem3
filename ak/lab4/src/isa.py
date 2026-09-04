from enum import Enum

class Opcode(str, Enum):

    # Работа с памаятью + регистры

    LDI = "LDI"             # Load Immediate: LDI R1, 10 (10 -> R1)
    LD = "LD"               # Load: LD R1, R2, offset (R1 -> Mem[R2+offset])
    ST = "ST"               # Store: ST R1, R2, offset (Mem[R2+offset] -> R1)

    # Арифметика (чисто регистры)

    ADD = "ADD"             # ADD R1, R2, R3 (R2 + R3 -> R1)
    SUB = "SUB"             # SUB R1, R2, R3 (R2 - R3 -> R1)
    MUL = "MUL"             # MUL R1, R2, R3 (R2 * R3 -> R1)
    DIV = "DIV"             # DIV R1, R2, R3 (R2 / R3 -> R1)
    MOD = "MOD"             # MOD R1, R2, R3 (R2 % R3 -> R1)
    CMP = "CMP"             # CMP R1, R2 (R2 - R3 -> NZVC)

    # Ветвления

    JMP = "JMP"             # Безусловный переход
    JZ = "JZ"               # Переход, если Z == 1 (Equal)
    JNZ = "JNZ"             # Переход, если Z == 0 (Not Equal)
    JL = "JL"               # Переход, если Меньше (Less)
    JLE = "JLE"             # Переход, если Меньше или Равно (Less or Equal)
    JG = "JG"               # Переход, если Больше (Greater)
    JGE = "JGE"             # Переход, если Больше или Равно (Greater or Equal)
    JC = "JC"               # Переход, если C == 1
    JNC = "JNC"             # Переход, если C == 0
    JV = "JV"               # Переход, если V == 1
    JNV = "JNV"             # Переход, если V == 0


    # Функция + Стек

    CALL = "CALL"           # CALL ADDR: вызов функции: PC + 1 -> SP; ADDR -> PC
    RET = "RET"             # Возврат из функции: LR -> PC
    PUSH = "PUSH"           # PUSH R1: R1 -> Mem[SP], SP - 1 -> SP
    POP = "POP"             # POP R1: SP + 1 -> SP, MEM[SP] -> R1

    # Порты + прерывания

    IN = "IN"               # IN R1, port_num
    OUT = "OUT"             # OUT port_num, R1
    IRET = "IRET"           # Возврат из прерывания + восстановления старых флагов: IRA -> PC

    # Прочее

    HLT = "HLT"             # Остановка процессора


class Instruction:

    # Будет запускаться каждый раз, когда будет создаваться объект класса Instruction
    def __init__(self, opcode: Opcode, args: list = None):
        self.opcode = opcode

        # Если аргументов нет, то делаем просто пустой список
        self.args = args if args is not None else []

    # Форматируем так, чтобы красиво отображалось
    def __repr__(self):
        args_str = ", ".join(map(str, self.args))
        return f"{self.opcode.value} {args_str}".strip()