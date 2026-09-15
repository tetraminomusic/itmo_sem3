# Одна физическая строка в кеш памяти
# При реализации кеша буду использовать Direct-Mapped кеш, мол, прямое отображение и тд. Реализуем через остаток от деления на 8


class CacheLine:
    def __init__(self):
        self.valid = False  # Флаг - есть ли в строке реальные и актуальные данные
        self.tag = None  # Адрес ячейки в оперативной памяти
        self.data = 0  # 32-битное значение из этой ячейки


# Сам великий и неповторимый кеш


class Cache:
    def __init__(self, memory: list, num_lines: int = 8):

        # Ссылаемся на ОЗУ

        self.memory = memory
        self.num_lines = num_lines

        self.lines = [CacheLine() for _ in range(num_lines)]

        # стата для логирования

        self.hits = 0
        self.misses = 0
        self.last_status = "NONE"

    # Функция чтения, возвращает [прочитанное значение, затраченные такты]

    def read(self, addr: int) -> tuple[int, int]:
        line_idx = addr % self.num_lines
        line = self.lines[line_idx]

        # Попадание

        if line.valid and line.tag == addr:
            self.hits += 1
            self.last_status = "HIT (1)"
            return line.data, 1

        # Промах

        self.misses += 1
        self.last_status = "MISS(10)"

        data_from_ram = self.memory[addr]

        line.valid = True
        line.tag = addr
        line.data = data_from_ram

        return data_from_ram, 10

    # сквозная запись. Возвращает затраченное время на запись

    def write(self, addr: int, val: int) -> int:
        line_idx = addr % self.num_lines
        line = self.lines[line_idx]

        # Пишем в ОЗУ

        self.memory[addr] = val

        # Если в кеше лежал адрес, который мы хотели записать

        if line.valid and line.tag == addr:
            line.data = val

        self.last_status = "WRITE(10)"
        return 10
