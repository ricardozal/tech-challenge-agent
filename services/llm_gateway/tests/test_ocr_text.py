"""OCR cleanup and its own generation limit (convergence T104)."""

from llm_gateway.ocr_text import first_copy
from llm_gateway.ollama_client import OCR_OPTIONS, OPTIONS

PAGE = "COMPROBANTE DE DOMICILIO\nTITULAR LAURA MÉNDEZ ROJAS\nC.P. 50000"


def test_repeated_page_keeps_the_first_copy():
    assert first_copy(f"{PAGE}\n{PAGE}\nCOMPROBANTE DE DOMI") == PAGE


def test_code_fence_and_duplicate_inside_it_are_dropped():
    assert first_copy(f"{PAGE}\n```markdown\n{PAGE}\n```") == PAGE
    assert first_copy(f"```markdown\n{PAGE}\n```") == PAGE


def test_text_without_repetition_is_unchanged():
    assert first_copy(PAGE) == PAGE


def test_ocr_has_a_larger_budget_than_extraction():
    assert OCR_OPTIONS["num_predict"] > OPTIONS["num_predict"]
    assert {k: OCR_OPTIONS[k] for k in ("temperature", "seed")} == {"temperature": 0, "seed": 42}
