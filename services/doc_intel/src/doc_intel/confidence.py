"""Deterministic per-field confidence (R-10).

- 0.0  value is null
- 0.3  value fails its format validator
- 0.95 format ok and the value is found in the OCR text
- 0.6  format ok but not found in the OCR text (possible hallucination of the extraction)
"""

import re
import unicodedata
from datetime import date
from typing import Any

NULL, BAD_FORMAT, SUPPORTED, UNSUPPORTED = 0.0, 0.3, 0.95, 0.6

CURP = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$")
POSTAL_CODE = re.compile(r"^\d{5}$")
VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
MONTHS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE",
          "NOVIEMBRE", "DICIEMBRE"]

DATE_FIELDS = {"fecha_nacimiento", "periodo_inicio", "periodo_fin", "fecha_emision"}
AMOUNT_FIELDS = {"ingreso_bruto", "ingreso_neto", "total_depositos", "saldo_final"}
YEAR_FIELDS = {"vigencia", "anio"}


def normalize(text: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]+", " ", plain)).strip()


def _digit_runs(text: str) -> set[str]:
    """Numbers as written in the OCR, without separators: '$9,200.00' -> '920000'."""
    return {re.sub(r"\D", "", run) for run in re.findall(r"\d[\d,.]*", text)}


def is_valid_format(name: str, value: Any) -> bool:
    if name == "curp":
        return bool(CURP.match(str(value).upper()))
    if name == "codigo_postal":
        return bool(POSTAL_CODE.match(str(value)))
    if name == "niv":
        return bool(VIN.match(str(value).upper()))
    if name == "moneda":
        return bool(CURRENCY.match(str(value).upper()))
    if name in AMOUNT_FIELDS:
        return isinstance(value, int | float) and value >= 0 and (value > 0 or name == "saldo_final")
    if name in YEAR_FIELDS:
        return isinstance(value, int) and 1950 <= value <= 2100
    if name in DATE_FIELDS:
        text = str(value)
        if name == "fecha_emision" and re.fullmatch(r"\d{4}", text):
            return True
        try:
            date.fromisoformat(text)
            return True
        except ValueError:
            return False
    if name == "periodicidad":
        return value in ("semanal", "quincenal", "mensual")
    return isinstance(value, str) and bool(value.strip())


def _date_forms(value: str) -> list[str]:
    if re.fullmatch(r"\d{4}", value):
        return [value]
    d = date.fromisoformat(value)
    return [
        f"{d.day:02d} {d.month:02d} {d.year}",
        f"{d.day} {d.month} {d.year}",
        f"{d.year} {d.month:02d} {d.day:02d}",
        f"{d.day} DE {MONTHS[d.month - 1]} DE {d.year}",
        f"{d.day:02d} DE {MONTHS[d.month - 1]} DE {d.year}",
        f"{d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}",
    ]


def is_supported(name: str, value: Any, ocr_text: str) -> bool:
    if name in AMOUNT_FIELDS:
        cents = f"{float(value):.2f}".replace(".", "")
        whole = str(int(float(value))) if float(value).is_integer() else None
        runs = _digit_runs(ocr_text)
        return cents in runs or (whole is not None and whole in runs)
    norm_ocr = f" {normalize(ocr_text)} "
    if name in DATE_FIELDS:
        return any(f" {form} " in norm_ocr for form in _date_forms(str(value)))
    if name == "periodicidad":
        return {"semanal": "SEMANAL", "quincenal": "QUINCENAL", "mensual": "MENSUAL"}[value] in norm_ocr
    needle = normalize(str(value))
    return bool(needle) and f" {needle} " in norm_ocr


def confidence(name: str, value: Any, ocr_text: str) -> float:
    if value is None:
        return NULL
    if not is_valid_format(name, value):
        return BAD_FORMAT
    return SUPPORTED if is_supported(name, value, ocr_text) else UNSUPPORTED
