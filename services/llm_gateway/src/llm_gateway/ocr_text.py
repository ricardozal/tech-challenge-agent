"""glm-ocr tends to repeat the whole page until the token limit and may wrap it in a code fence.
Keep the first copy only (same cleanup that eval/ applies to its recorded OCR files)."""

FENCE = "```"


def first_copy(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    first = next((line.strip() for line in lines if line.strip() and not line.startswith(FENCE)), None)
    for line in lines:
        if line.startswith(FENCE):
            if kept:
                break
            continue
        if kept and first is not None and line.strip() == first:
            break
        kept.append(line)
    return "\n".join(kept).strip()
