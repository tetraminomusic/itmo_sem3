import logging

from cache import Cache
from datapath import DataPath
from isa import Instruction, Opcode

# Устройство управления типа Hardwired


class ControlUnit:
    def __init__(self, data_path: DataPath, schedule: list | None = None):
        self.dp = data_path
        self.cache = Cache(self.dp.memory)
        self.current_tick = 0  # Счётчик прошедших тактов
        self.instruction_counter = 0  # Сколько инструкций выполнили
        self.is_halted = False  # Флаг остановки для команды HLT

        # Расписание прерываний

        self.schedule = schedule if schedule is not None else []

        self.check_interrupt_schedule()

    def check_interrupt_schedule(self):
        while self.schedule and self.current_tick >= self.schedule[0][0]:
            _, char = self.schedule.pop(0)
            ascii_code = ord(char) if isinstance(char, str) else int(char)

            self.dp.port_0_in.append(ascii_code)

            char_repr = (
                chr(ascii_code) if 32 <= ascii_code <= 126 else f"\\x{ascii_code:02x}"
            )
            logging.info(
                "[ТАКТ %d] ВУ прислало символ '%s' (ASCII %d), провод IntRq = 1!",
                self.current_tick,
                char_repr,
                ascii_code,
            )

    def tick(self):  # Один такт тактового генератора
        self.current_tick += 1

    def __repr__(self):
        """Возвращает строку с текущими значениями для табличного вывода."""
        nzcv = f"{self.dp.status_register & 0xF:04b}"

        word = self.dp.cr
        if isinstance(word, Instruction):
            instr_str = str(word)
            hex_str = f"{word.encode():08X}"
        elif isinstance(word, int):
            op_code = (word >> 24) & 0xFF
            try:
                op_name = Opcode(op_code).name
                rd = (word >> 20) & 0xF
                rs1 = (word >> 16) & 0xF
                imm = word & 0xFFFF
                instr_str = f"{op_name} R{rd}, R{rs1}, {imm}"
            except ValueError:
                instr_str = "DATA"
            hex_str = f"{word:08X}" if word else "00000000"
        else:
            instr_str = "NONE"
            hex_str = "00000000"

        return (
            f"| {self.current_tick:^6} "
            f"| {self.dp.pc:^4} "
            f"| {hex_str:^8} "
            f"| {instr_str:<22} "
            f"| {self.dp.read_reg('R1'):^6} "
            f"| {self.dp.read_reg('R2'):^6} "
            f"| {self.dp.sp:^6} "
            f"| {nzcv:^6} "
            f"| {self.cache.last_status:^9} |"
        )

    def step(self):  # Выполнение одной инструкции от корки до корки
        if self.is_halted or not self.dp.flag_p:
            return

        # Проверяем текущее расписание прерываний

        self.check_interrupt_schedule()

        # Interruption Fetch (проверка прерывания через схему И: IntRq & EI)

        if self.dp.irq:
            self.handle_interrupt()

        # Instruction Fetch (Выборка команды через КЭШ в регистр cr)

        raw_word, wait_ticks = self.cache.read(self.dp.pc)
        self.current_tick += wait_ticks
        self.dp.cr = raw_word

        # Если дошли до пустой ячейки
        if self.dp.cr == 0 or self.dp.cr is None:
            self.is_halted = True
            self.dp.flag_p = 0
            return

        # Decode (Универсальный аппаратный декодер 32 бит!)
        if isinstance(self.dp.cr, Instruction):
            op = self.dp.cr.opcode
            args = self.dp.cr.args
            rd = args[0] if len(args) > 0 else "R0"
            rs1 = args[1] if len(args) > 1 else "R0"
            imm = args[2] if len(args) > 2 else 0
        else:
            op_val = (self.dp.cr >> 24) & 0xFF
            if op_val == Opcode.HLT or op_val == 0:
                self.is_halted = True
                self.dp.flag_p = 0
                return
            op = Opcode(op_val)
            rd_idx = (self.dp.cr >> 20) & 0xF
            rs1_idx = (self.dp.cr >> 16) & 0xF
            rs2_idx = (self.dp.cr >> 12) & 0xF
            imm = self.dp.cr & 0xFFFF
            rd = f"R{rd_idx}"
            rs1 = f"R{rs1_idx}"

        # Останов при встрече HLT
        if op == Opcode.HLT:
            self.is_halted = True
            self.dp.flag_p = 0
            return

        next_pc = self.dp.pc + 1

        # Execute
        # Работа с памятью и константами

        if op == Opcode.LDI:
            number = imm if not isinstance(self.dp.cr, Instruction) else args[1]
            self.dp.write_reg(rd, number)
            self.tick()

        elif op == Opcode.ST:
            val = self.dp.read_reg(rd)
            base_addr = self.dp.read_reg(rs1)
            offset = imm if not isinstance(self.dp.cr, Instruction) else args[2]

            # Пишем через кеш
            wait_ticks = self.cache.write(base_addr + offset, val)
            self.current_tick += wait_ticks

        elif op == Opcode.LD:
            base_addr = self.dp.read_reg(rs1)
            offset = imm if not isinstance(self.dp.cr, Instruction) else args[2]

            # Читаем через кеш
            val, wait_ticks = self.cache.read(base_addr + offset)
            self.dp.write_reg(rd, val)
            self.current_tick += wait_ticks

        # Арифметика бинарная

        elif op in (
            Opcode.ADD,
            Opcode.SUB,
            Opcode.MUL,
            Opcode.DIV,
            Opcode.MOD,
            Opcode.AND,
            Opcode.OR,
            Opcode.XOR,
            Opcode.LSL,
            Opcode.LSR,
            Opcode.CMP,
        ):
            if isinstance(self.dp.cr, Instruction):
                r_dest = args[0]
                if op == Opcode.CMP:
                    v1 = self.dp.read_reg(args[0])
                    v2 = self.dp.read_reg(args[1])
                else:
                    v1 = self.dp.read_reg(args[1])
                    v2 = self.dp.read_reg(args[2])
            else:
                r_dest = f"R{rd_idx}"
                if op == Opcode.CMP:
                    # У CMP всего 2 операнда: rd и rs1
                    v1 = self.dp.read_reg(f"R{rd_idx}")
                    v2 = self.dp.read_reg(f"R{rs1_idx}")
                else:
                    # У 3-регистровых команд (ADD R1, R2, R0) операнды лежат в rs1 и rs2
                    v1 = self.dp.read_reg(f"R{rs1_idx}")
                    v2 = self.dp.read_reg(f"R{rs2_idx}")

            if op == Opcode.CMP:
                self.dp.execute_alu(op, v1, v2)
            else:
                result = self.dp.execute_alu(op, v1, v2)
                self.dp.write_reg(r_dest, result)

            self.tick()

        elif op in (Opcode.INC, Opcode.DEC):
            val = self.dp.read_reg(rd)
            res = self.dp.execute_alu(op, val)
            self.dp.write_reg(rd, res)
            self.tick()

        elif op == Opcode.NOT:
            val = self.dp.read_reg(rs1)
            res = self.dp.execute_alu(op, val)
            self.dp.write_reg(rd, res)
            self.tick()

        # Ветвления (Каноничный набор)

        elif (
            op == Opcode.JMP
            or op == Opcode.JZ
            and self.dp.flag_z == 1
            or op == Opcode.JNZ
            and self.dp.flag_z == 0
            or op == Opcode.JL
            and (self.dp.flag_n != self.dp.flag_v)
            or op == Opcode.JGE
            and (self.dp.flag_n == self.dp.flag_v)
        ):
            next_pc = imm if not isinstance(self.dp.cr, Instruction) else args[0]
            self.tick()

        # Функции + Стек (прямой аппаратный стек!)

        elif op == Opcode.CALL:
            target_addr = imm if not isinstance(self.dp.cr, Instruction) else args[0]
            self.dp.memory[self.dp.sp] = next_pc
            self.dp.sp -= 1
            next_pc = target_addr
            self.tick()

        elif op == Opcode.RET:
            self.dp.sp += 1
            next_pc = self.dp.memory[self.dp.sp]
            self.tick()

        elif op == Opcode.PUSH:
            val = self.dp.read_reg(rd)
            self.dp.memory[self.dp.sp] = val
            self.dp.sp -= 1
            self.tick()

        elif op == Opcode.POP:
            self.dp.sp += 1
            val = self.dp.memory[self.dp.sp]
            self.dp.write_reg(rd, val)
            self.tick()

        # Порты ввода/вывода

        elif op == Opcode.OUT:
            if isinstance(self.dp.cr, Instruction):
                port = args[0]
                val = self.dp.read_reg(args[1])
            else:
                port = imm
                val = self.dp.read_reg(f"R{rd_idx}")

            if port == 1:
                self.dp.port_1_out.append(val)
            self.tick()

        elif op == Opcode.IN:
            if isinstance(self.dp.cr, Instruction):
                target_reg = args[0]
            else:
                target_reg = f"R{rd_idx}"

            val = self.dp.port_0_in.pop(0) if self.dp.port_0_in else 0

            self.dp.write_reg(target_reg, val)
            self.tick()

        # Прерывания

        elif op == Opcode.IRET:
            self.dp.sp += 1
            self.dp.status_register = self.dp.memory[self.dp.sp]
            self.dp.sp += 1
            next_pc = self.dp.memory[self.dp.sp]

            self.dp.flag_ie = 1

            self.tick()

        elif op == Opcode.EI:
            self.dp.flag_ie = 1
            self.tick()

        elif op == Opcode.DI:
            self.dp.flag_ie = 0
            self.tick()

        # Обновляем PC напрямую

        self.dp.pc = next_pc
        self.instruction_counter += 1

    # Обработка прерывания (аппаратное сохранение PC в стек)

    def handle_interrupt(self, vector_address: int = 1):
        self.dp.memory[self.dp.sp] = self.dp.pc
        self.dp.sp -= 1

        self.dp.memory[self.dp.sp] = self.dp.status_register
        self.dp.sp -= 1

        self.dp.flag_ie = 0

        self.dp.pc = vector_address
        self.tick()
