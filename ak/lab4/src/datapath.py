from isa import Opcode

# Класс, отвечающий за физические компоненты процессора - память, регистровый файл, АЛУ, Флаги и Порты ввода-вывода


class DataPath:
    # Что у нас будет инициализировать в общем-то

    def __init__(self, memory_size: int = 4096):

        # В начале расположим инструкции, опосля строки и переменные и с конца будет расти у нас великий и ужасный стек

        self.memory = [0] * memory_size  # RAM

        # Чистый регистровый файл: строго R0..R15! R0 заземлен на 0
        self.registers = [0] * 16  # REG (R0 - R15)

        # Служебные регистры вынесены ОТДЕЛЬНО (как просил лектор!)
        self.pc = 0  # Счётчик команд (PC)
        self.sp = memory_size - 1  # Указатель на вершину стека (SP, 4095)
        self.cr = 0  # Регистр команд (CR / IR)
        self.status_register = 0  # Регистр состояния процессора (PS)

        self.port_0_in: list[int] = []  # Буфер входных символов
        self.port_1_out: list[int] = []  # Буфер вывода на экран
        # Сигнал о запросе прерывания от ВУ

        self.flag_w = 1  # Процессор находится в непрерывном режиме
        self.flag_p = 1  # Процессор работает
        self.flag_ie = 0  # Прерывания по дефолту разрешены

    # Регистр состояния со слайда лекции (NZCV, EI, W, P)

    @property  # C
    def flag_c(self) -> int:
        return (self.status_register >> 0) & 1

    @flag_c.setter
    def flag_c(self, val: int):
        if val:
            self.status_register |= 1 << 0
        else:
            self.status_register &= ~(1 << 0)

    @property  # V
    def flag_v(self) -> int:
        return (self.status_register >> 1) & 1

    @flag_v.setter
    def flag_v(self, val: int):
        if val:
            self.status_register |= 1 << 1
        else:
            self.status_register &= ~(1 << 1)

    @property  # Z
    def flag_z(self) -> int:
        return (self.status_register >> 2) & 1

    @flag_z.setter
    def flag_z(self, val: int):
        if val:
            self.status_register |= 1 << 2
        else:
            self.status_register &= ~(1 << 2)

    @property  # N
    def flag_n(self) -> int:
        return (self.status_register >> 3) & 1

    @flag_n.setter
    def flag_n(self, val: int):
        if val:
            self.status_register |= 1 << 3
        else:
            self.status_register &= ~(1 << 3)

            # 0 - резерв

    @property  # IE - запрет/разрешения прерывания
    def flag_ie(self) -> int:
        return (self.status_register >> 5) & 1

    @flag_ie.setter
    def flag_ie(self, val: int):
        if val:
            self.status_register |= 1 << 5
        else:
            self.status_register &= ~(1 << 5)

    @property  # IRQ
    def irq(self) -> int:
        return 1 if (self.dev_signal and self.flag_ie) else 0

    @property
    def dev_signal(self) -> int:
        return 1 if len(self.port_0_in) > 0 else 0

    @property  # W (1 - непрерывный режим, 0 - потактовый режим)
    def flag_w(self) -> int:
        return (self.status_register >> 7) & 1

    @flag_w.setter
    def flag_w(self, val: int):
        if val:
            self.status_register |= 1 << 7
        else:
            self.status_register &= ~(1 << 7)

    @property  # P (Работа/Останов)
    def flag_p(self) -> int:
        return (self.status_register >> 8) & 1

    @flag_p.setter
    def flag_p(self, val: int):
        if val:
            self.status_register |= 1 << 8
        else:
            self.status_register &= ~(1 << 8)

    # Регистровые файлы (строго R0..R15)

    def get_reg_idx(
        self, reg_name: str
    ) -> int:  # Превращает имя регистра в индекс 0..15
        return int(reg_name.replace("R", ""))

    def read_reg(
        self, reg_name: str
    ) -> int:  # Возвращает 32-битное значение из регистра
        idx = self.get_reg_idx(reg_name)
        return self.registers[idx]

    def write_reg(
        self, reg_name: str, value: int
    ):  # Записывает 32-битное значение в регистр
        idx = self.get_reg_idx(reg_name)

        # В R0 нельзя ничего записать
        if idx == 0:
            return

        self.registers[idx] = value & 0xFFFF_FFFF

    # АЛУ

    def execute_alu(self, op: Opcode, src1: int, src2: int = 0) -> int:

        res = 0

        # Арифметика

        if op == Opcode.ADD:
            res = src1 + src2
        elif op in (Opcode.SUB, Opcode.CMP):
            res = src1 - src2
        elif op == Opcode.MUL:
            res = src1 * src2
        elif op == Opcode.DIV:
            res = src1 // src2 if src2 != 0 else 0
        elif op == Opcode.MOD:
            res = src1 % src2 if src2 != 0 else 0
        elif op == Opcode.INC:
            res = src1 + 1
        elif op == Opcode.DEC:
            res = src1 - 1

        # Логические операции

        elif op == Opcode.AND:
            res = src1 & src2
        elif op == Opcode.OR:
            res = src1 | src2
        elif op == Opcode.XOR:
            res = src1 ^ src2
        elif op == Opcode.NOT:
            res = ~src1

        # Сдвиги

        elif op == Opcode.LSL:
            res = (src1 << (src2 & 31)) & 0xFFFF_FFFF
        elif op == Opcode.LSR:
            res = (src1 & 0xFFFF_FFFF) >> (src2 & 31)

        # NZVC

        self.flag_n = 1 if (res & (1 << 31)) != 0 else 0  # N
        self.flag_z = 1 if (res & 0xFFFF_FFFF) == 0 else 0  # Z
        self.flag_c = 1 if (res > 0xFFFF_FFFF) else 0  # C

        if op in (Opcode.ADD, Opcode.INC):  # V
            self.flag_v = 1 if (~(src1 ^ src2) & (src1 ^ res) & 0x80000000) != 0 else 0
        elif op in (Opcode.SUB, Opcode.CMP, Opcode.DEC):
            self.flag_v = 1 if ((src1 ^ src2) & (src1 ^ res) & 0x80000000) != 0 else 0
        else:
            self.flag_v = 0

        return res & 0xFFFF_FFFF
