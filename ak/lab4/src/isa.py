from enum import IntEnum


class Opcode(IntEnum):
    # Работа с памятью + регистры

    LDI = 0x01  # 0000 0001 - Load Immediate: LDI R1, 10 (10 -> R1)
    LD = 0x02  # 0000 0010 - Load: LD R1, R2, offset (R1 -> Mem[R2+offset])
    ST = 0x03  # 0000 0011 - Store: ST R1, R2, offset (Mem[R2+offset] -> R1)

    # Арифметика (чисто регистры)

    ADD = 0x04  # 0000 0100 - ADD R1, R2, R3 (R2 + R3 -> R1)
    SUB = 0x05  # 0000 0101 - SUB R1, R2, R3 (R2 - R3 -> R1)
    MUL = 0x06  # 0000 0110 - MUL R1, R2, R3 (R2 * R3 -> R1)
    DIV = 0x07  # 0000 0111 - DIV R1, R2, R3 (R2 / R3 -> R1)
    MOD = 0x08  # 0000 1000 - MOD R1, R2, R3 (R2 % R3 -> R1)
    INC = 0x09  # 0000 1001 - INC R1 (R1 + 1 -> R1)
    DEC = 0x0A  # 0000 1010 - DEC R1 (R1 - 1 -> R1)
    CMP = 0x0B  # 0000 1011 - CMP R1, R2 (R1 - R2 -> NZVC)

    # Логические операции

    AND = 0x0C  # 0000 1100 - AND R1, R2, R3 (R2 & R3 -> R1)
    OR = 0x0D  # 0000 1101 - OR R1, R2, R3 (R2 | R3 -> R1)
    XOR = 0x0E  # 0000 1110 - XOR R1, R2, R3 (R2 ^ R3 -> R1)
    NOT = 0x0F  # 0000 1111 - NOT R1, R2 (~R2 -> R1)

    # Логические сдвиги

    LSL = 0x10  # 0001 0000 - Logical Shift Left (R2 << R3 -> R1)
    LSR = 0x11  # 0001 0001 - Logical Shift Right (R2 >> R3 -> R1, с нулями)

    # Ветвления (Минимальный каноничный набор RISC)

    JMP = 0x12  # 0001 0010 - Безусловный переход
    JZ = 0x13  # 0001 0011 - Переход, если Z == 1 (Equal)
    JNZ = 0x14  # 0001 0100 - Переход, если Z == 0 (Not Equal)
    JL = 0x15  # 0001 0101 - Переход, если Меньше (N != V)
    JGE = 0x16  # 0001 0110 - Переход, если Больше или Равно (N == V)

    # Функция + Стек

    CALL = 0x17  # 0001 0111 - CALL ADDR: вызов функции: next_pc -> Stack; ADDR -> PC
    RET = 0x18  # 0001 1000 - Возврат из функции: Stack -> PC
    PUSH = 0x19  # 0001 1001 - PUSH R1: R1 -> Mem[SP], SP - 1 -> SP
    POP = 0x1A  # 0001 1010 - POP R1: SP + 1 -> SP, MEM[SP] -> R1

    # Порты + прерывания

    IN = 0x1B  # 0001 1011 - IN R1, port_num
    OUT = 0x1C  # 0001 1100 - OUT port_num, R1
    EI = 0x1D  # 0001 1101 - Enable Interrupts (разрешить прерывания: IE = 1)
    DI = 0x1E  # 0001 1110 - Disable Interrupts (запретить прерывания: IE = 0)
    IRET = 0x1F  # 0001 1111 - Возврат из прерывания: Stack -> PC, Stack -> PS

    # Прочее

    HLT = 0x20  # 0010 0000 - Остановка процессора


class Instruction:
    def __init__(self, opcode: Opcode, args: list | None = None):
        self.opcode = opcode
        self.args = args if args is not None else []

    def __repr__(self):
        args_str = ", ".join(map(str, self.args))
        return f"{self.opcode.name} {args_str}".strip()

    def encode(self) -> int:
        op_code_num = int(self.opcode) & 0xFF

        rd = 0
        rs1 = 0
        rs2 = 0
        imm = 0

        reg_args = []
        for arg in self.args:
            if isinstance(arg, str) and arg.startswith("R"):
                reg_args.append(int(arg.replace("R", "")))
            elif isinstance(arg, int):
                imm = arg & 0xFFFF

        if len(reg_args) == 1:
            rd = reg_args[0]
        elif len(reg_args) == 2:
            rd = reg_args[0]
            rs1 = reg_args[1]
        elif len(reg_args) >= 3:
            rd = reg_args[0]
            rs1 = reg_args[1]
            rs2 = reg_args[2]

        # Для 3-регистровых инструкций (ADD R1, R2, R0) сохраняем rs2 в биты [15:12]

        if len(reg_args) >= 3:
            word = (op_code_num << 24) | (rd << 20) | (rs1 << 16) | (rs2 << 12)
        else:
            word = (op_code_num << 24) | (rd << 20) | (rs1 << 16) | imm

        return word
