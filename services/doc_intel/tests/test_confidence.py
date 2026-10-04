"""Deterministic per-field confidence (R-10)."""

import pytest

from doc_intel.confidence import BAD_FORMAT, NULL, SUPPORTED, UNSUPPORTED, confidence

OCR = """IDENTIFICACIÓN — ESPÉCIMEN DE PRUEBA
NOMBRE(S) LAURA  APELLIDOS MÉNDEZ ROJAS
CURP MERL880412MMCNJR09
FECHA DE NACIMIENTO 12/04/1988
VIGENCIA 2031
NETO A PAGAR $9,200.00 MXN
FECHA DE EMISIÓN 5 de septiembre de 2026"""


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("curp", None, NULL),
        ("curp", "MERL88", BAD_FORMAT),
        ("codigo_postal", "5000", BAD_FORMAT),
        ("niv", "3VWEJ1BU0KM12345", BAD_FORMAT),
        ("fecha_nacimiento", "12/04/1988", BAD_FORMAT),
        ("ingreso_neto", -5.0, BAD_FORMAT),
        ("curp", "MERL880412MMCNJR09", SUPPORTED),
        ("fecha_nacimiento", "1988-04-12", SUPPORTED),
        ("fecha_emision", "2026-09-05", SUPPORTED),
        ("vigencia", 2031, SUPPORTED),
        ("ingreso_neto", 9200.0, SUPPORTED),
        ("moneda", "MXN", SUPPORTED),
        ("curp", "MERL880412MMCNJR01", UNSUPPORTED),
        ("ingreso_neto", 9800.0, UNSUPPORTED),
        ("nombre_completo", "JORGE RAMÍREZ", UNSUPPORTED),
    ],
)
def test_confidence_levels(name, value, expected):
    assert confidence(name, value, OCR) == expected
