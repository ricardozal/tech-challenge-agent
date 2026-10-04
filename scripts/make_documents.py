"""Render the synthetic test documents of fixtures/documents/specs.yaml as PNG (Principle X).

Every document carries the "ESPÉCIMEN DE PRUEBA — DATOS FICTICIOS" banner. Run make seed-fixtures
afterwards: the OCR fixtures are keyed by the sha256 of each PNG.
"""

import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "fixtures" / "documents"
BANNER = "ESPÉCIMEN DE PRUEBA — DATOS FICTICIOS"
FONTS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(size: int) -> ImageFont.ImageFont:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def load_specs() -> dict:
    return yaml.safe_load((DOCS / "specs.yaml").read_text(encoding="utf-8"))["documents"]


def ocr_text(spec: dict) -> str:
    """Exactly what the PNG shows, banner included; recorded as the OCR fixture."""
    return "\n".join([BANNER, *spec["lines"]])


def render(spec: dict) -> Image.Image:
    lines = ocr_text(spec).split("\n")
    body, banner = font(26), font(22)
    image = Image.new("RGB", (1100, 90 + 46 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1100, 50], fill=(200, 30, 30))
    draw.text((24, 12), BANNER, fill="white", font=banner)
    for i, line in enumerate(lines[1:], start=1):
        draw.text((24, 30 + 46 * i), line, fill="black", font=body)
    if spec.get("blur"):
        image = image.filter(ImageFilter.GaussianBlur(4))
    return image


def main() -> int:
    for name, spec in load_specs().items():
        path = DOCS / f"{name}.png"
        render(spec).save(path, format="PNG", optimize=False)
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
