import argparse
import logging
import struct
import sys

from controlunit import ControlUnit
from datapath import DataPath

# Загружает бинарник с диска и запускает процессор


def run_simulation(binary_file: str, schedule: list, max_ticks: int = 2000):
    dp = DataPath(4096)

    # Читаем 32-битные слова из файла обратно в память

    with open(binary_file, "rb") as f:
        for i in range(4096):
            chunk = f.read(4)
            if not chunk:
                break
            word = struct.unpack(">I", chunk)[0]
            dp.memory[i] = word

    cu = ControlUnit(dp, schedule=schedule)

    logging.info("\nЗапуск процесса by tetramino")

    header = (
        f"| {'TICK':^6} "
        f"| {'PC':^4} "
        f"| {'HEX CODE':^8} "
        f"| {'INSTRUCTION':<22} "
        f"| {'R1':^6} "
        f"| {'R2':^6} "
        f"| {'SP':^6} "
        f"| {'NZVC':^6} "
        f"| {'CACHE':^9} |"
    )

    separator = "-" * len(header)

    logging.debug(separator)
    logging.debug(header)
    logging.debug(separator)

    # Главный цикл симуляции
    try:
        while not cu.is_halted and cu.current_tick <= max_ticks:
            logging.debug("%s", cu)
            cu.step()
    except EOFError:
        logging.warning("Ошибка: буфер ввода пуст, но программа запрашивает IN")

    if cu.current_tick >= max_ticks:
        logging.warning("Превышен лимит тактов, процессор принудительно остановлен")

    # Собираем вывод из порта 1

    output_chars = ""
    for c in dp.port_1_out:
        if 32 <= c <= 126 or c == 10:
            output_chars += chr(c)
        else:
            output_chars += f"\\x{c:02x}"

    logging.info(separator)
    logging.info("Процессор остановлен, выполнено тактов: %d", cu.current_tick)
    logging.info("Выполнено инструкций: %d", cu.instruction_counter)
    logging.info("Вывод в порт 1:")

    print("\n" + "=" * 40)
    print(output_chars)
    print("=" * 40 + "\n")

    total_requests = cu.cache.hits + cu.cache.misses
    hit_rate = (cu.cache.hits / total_requests * 100) if total_requests > 0 else 0
    logging.info("Статистика кеш-попаданий:")
    logging.info(
        "Попаданий (Hits): %d | Промахов (Misses): %d | Hit Rate: %.2f%%",
        cu.cache.hits,
        cu.cache.misses,
        hit_rate,
    )

    return output_chars, cu.current_tick


# Точка входа в программу


def main():
    parser = argparse.ArgumentParser(
        description="Симулятор RISC-процессора by tetramino"
    )

    parser.add_argument(
        "-c",
        "--code",
        required=True,
        help="Путь к бинарному файлу с машинным кодом (.bin)",
    )

    parser.add_argument(
        "-i",
        "--input",
        default=None,
        help="Путь к текстовому файлу с входными данными (опционально)",
    )

    parser.add_argument(
        "-t",
        "--ticks",
        type=int,
        default=5000,
        help="Лимит тактов симуляции (по умолчанию 5000)",
    )

    args = parser.parse_args()

    # Оставляем чистый формат логов
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    # Формируем расписание прерываний из файла

    schedule = []
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("["):
                    import json

                    schedule = json.loads(content)
                else:
                    current_tick = 50
                    for char in content:
                        schedule.append((current_tick, char))
                        current_tick += 100
        except FileNotFoundError:
            print(f"Ошибка: файл ввода '{args.input}' не найден", file=sys.stderr)
            sys.exit(1)

    # Запуск симуляции

    try:
        run_simulation(args.code, schedule, max_ticks=args.ticks)
    except Exception as e:
        print(f"Произошла ошибка во время симуляции: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
