# tests/test_golden.py
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import translator
from machine import run_simulation


@pytest.mark.golden_test("golden/*.yml")
def test_golden(golden, tmp_path):

    # Интеграционный Golden-тест с автообновлением эталонов.
    lisp_code = golden["in_source"]
    _ = golden.get("in_stdin", "")

    source_file = tmp_path / "program.lisp"
    bin_file = tmp_path / "program.bin"
    listing_file = tmp_path / "listing.txt"
    source_file.write_text(lisp_code, encoding="utf-8")

    # Компиляция
    translator.compile_file(str(source_file), str(bin_file), str(listing_file))
    listing_content = listing_file.read_text(encoding="utf-8").strip()

    # Симуляция
    output, _ = run_simulation(str(bin_file), schedule=[], max_ticks=5000)

    # Передаем реальные результаты в pytest-golden
    golden.out["out_code_hex"] = listing_content
    golden.out["out_stdout"] = output.strip()

    # Сверка с эталоном
    assert listing_content == golden.out["out_code_hex"].strip()
    assert output.strip() == golden.out["out_stdout"].strip()
