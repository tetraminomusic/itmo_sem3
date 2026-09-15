# tests/test_machine.py
import os
import sys

# Добавляем путь к папке src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import translator
from cache import Cache
from isa import Opcode
from machine import ControlUnit, DataPath, run_simulation


def test_cache_hit_and_miss_latencies():
    """Задержки: промах = 10 тактов, попадание = 1 такт."""
    memory = [0] * 4096
    memory[100] = 42
    cache = Cache(memory, num_lines=8)

    val1, ticks1 = cache.read(100)
    assert val1 == 42
    assert ticks1 == 10
    assert cache.misses == 1
    assert cache.hits == 0

    val2, ticks2 = cache.read(100)
    assert val2 == 42
    assert ticks2 == 1
    assert cache.misses == 1
    assert cache.hits == 1


def test_cache_write_through():
    """Сквозная запись: пишет и в память, и обновляет строку кэша."""
    memory = [0] * 4096
    cache = Cache(memory, num_lines=8)

    cache.read(50)
    ticks = cache.write(50, 999)
    assert ticks == 10
    assert memory[50] == 999

    val, read_ticks = cache.read(50)
    assert val == 999
    assert read_ticks == 1


def test_cache_eviction():
    """Вытеснение кэша (Eviction): 8 строк, 9-я должна перезаписать 1-ю."""
    memory = [0] * 4096
    cache = Cache(memory, num_lines=8)

    # Заполняем все 8 строк кэша (адреса 0..7)
    for i in range(8):
        cache.read(i)

    # Читаем адрес 8 (8 % 8 = 0). Он вытесняет строку 0!
    cache.read(8)

    # Снова читаем адрес 0 — должен быть промах (10 тактов), так как строка была вытеснена!
    _, ticks = cache.read(0)
    assert ticks == 10


def test_alu_flags_nzcv():
    """Проверка выставления флагов NZCV."""
    dp = DataPath()

    # Флаг Z (Zero)
    dp.execute_alu(Opcode.SUB, 10, 10)
    assert dp.flag_z == 1
    assert dp.flag_n == 0

    # Флаг N (Negative)
    dp.execute_alu(Opcode.SUB, 5, 10)
    assert dp.flag_n == 1
    assert dp.flag_z == 0

    # Флаг C (Carry)
    dp.execute_alu(Opcode.ADD, 0xFFFFFFFF, 1)
    assert dp.flag_c == 1

    # Флаг V (Overflow)
    dp.execute_alu(Opcode.ADD, 0x7FFFFFFF, 1)
    assert dp.flag_v == 1


def test_alu_division_by_zero():
    """Защита от деления на ноль в АЛУ."""
    dp = DataPath()
    res = dp.execute_alu(Opcode.DIV, 100, 0)
    assert res == 0


def test_r0_hardwired_zero():
    """Регистр R0 невозможно перезаписать (всегда 0)."""
    dp = DataPath()
    dp.write_reg("R0", 999)
    assert dp.read_reg("R0") == 0


def test_arithmetic_execution(tmp_path):
    """Тест выполнения арифметических инструкций процессором."""
    source_file = tmp_path / "math.lisp"
    bin_file = tmp_path / "math.bin"

    # 65 + 5 - 4 = 66 (буква 'B')
    source_file.write_text(
        """
    (progn
        (setq res (- (+ 65 5) 4))
        (out 1 res)
    )
    """,
        encoding="utf-8",
    )

    translator.compile_file(str(source_file), str(bin_file))
    output, _ = run_simulation(str(bin_file), schedule=[], max_ticks=300)
    assert output == "B"


def test_functions_and_recursion_execution(tmp_path):
    """Тест рекурсии с аккумулятором (Tail Recursion) через аппаратный стек."""
    source_file = tmp_path / "fact.lisp"
    bin_file = tmp_path / "fact.bin"

    # Считаем сумму чисел 3 + 2 + 1 = 6. Начинаем с 60: итог 66 ('B')
    source_file.write_text(
        """
    (progn
        (defun sum (n acc)
            (if (<= n 0)
                acc
                (sum (- n 1) (+ acc n))))

        (setq ans (sum 3 60))
        (out 1 ans)
    )
    """,
        encoding="utf-8",
    )

    translator.compile_file(str(source_file), str(bin_file))
    output, _ = run_simulation(str(bin_file), schedule=[], max_ticks=1000)
    assert output == "B"


def test_pascal_string_traversal_with_aref(tmp_path):
    """Тест чтения Pascal-строки через команду aref."""
    source_file = tmp_path / "str.lisp"
    bin_file = tmp_path / "str.bin"

    source_file.write_text(
        """
    (progn
        (setq s "OK")
        (out 1 (aref s 1))
        (out 1 (aref s 2))
    )
    """,
        encoding="utf-8",
    )

    translator.compile_file(str(source_file), str(bin_file))
    output, _ = run_simulation(str(bin_file), schedule=[], max_ticks=300)
    assert output == "OK"


def test_deep_recursion_stack_growth(tmp_path):
    """Стек должен расти вниз и выдерживать глубокую рекурсию."""
    source_file = tmp_path / "deep.lisp"
    bin_file = tmp_path / "deep.bin"

    source_file.write_text(
        """
    (progn
        (defun deep (n val)
            (if (<= n 0)
                val
                (deep (- n 1) val)))
        (out 1 (deep 15 65))
    )
    """,
        encoding="utf-8",
    )

    translator.compile_file(str(source_file), str(bin_file))
    output, _ = run_simulation(str(bin_file), schedule=[], max_ticks=8000)
    assert output == "A"


def test_input_buffer_empty():
    """Если буфер порта 0 пуст, чтение возвращает 0."""
    dp = DataPath()
    cu = ControlUnit(dp)

    # 0x1B100000 = IN R1, 0
    dp.memory[0] = 0x1B100000
    cu.step()
    assert dp.read_reg("R1") == 0


def test_timeout_execution(tmp_path):
    """Остановка симулятора по превышению лимита тактов (бесконечный цикл)."""
    source_file = tmp_path / "inf.lisp"
    bin_file = tmp_path / "inf.bin"

    source_file.write_text(
        """
    (progn
        (defun inf () (inf))
        (inf)
    )
    """,
        encoding="utf-8",
    )

    translator.compile_file(str(source_file), str(bin_file))
    _, ticks = run_simulation(str(bin_file), schedule=[], max_ticks=150)
    assert ticks >= 150
