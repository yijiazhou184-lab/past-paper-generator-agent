"""Decide whether a unit of evidence can be understood from extracted text or needs its page image.

The rules read only layout labels and text volume, never the subject, course or filename. Uncertain
pages go to the visual route: a missed page silently loses content, an extra page only costs a call.
"""

RULE_VERSION = "pdf-route-1"
SIGNALS = ("empty_formula_region", "large_figure", "table_region", "low_text_density",
           "full_page_image", "model_requested", "manual")
# PDF points squared. A4 is about 501k and a 4:3 slide about 389k; logos and icons stay below.
LARGE_FIGURE_AREA = 20000
FULL_PAGE_FIGURE_AREA = 250000
LOW_TEXT_CHARS = 80


def area(block):
    box = block.get("bbox") or {}
    try:
        return abs((box["r"] - box["l"]) * (box["t"] - box["b"]))
    except (KeyError, TypeError):
        # A figure without a usable box cannot be proven small (nor claimed to fill the page).
        return LARGE_FIGURE_AREA + 1


def route_page(physical_page, blocks, text, extra_signals=()):
    kinds = [(str(b.get("kind", "")).lower(), b) for b in blocks]
    signals = []
    if any("formula" in kind and not (b.get("text") or "").strip() for kind, b in kinds):
        signals.append("empty_formula_region")
    figures = [area(b) for kind, b in kinds if "picture" in kind or "chart" in kind]
    if any(a > LARGE_FIGURE_AREA for a in figures):
        signals.append("large_figure")
    if any("table" in kind for kind, _ in kinds):
        signals.append("table_region")
    sparse = len((text or "").strip()) < LOW_TEXT_CHARS
    if sparse:
        signals.append("low_text_density")
    if sparse and any(a >= FULL_PAGE_FIGURE_AREA for a in figures):
        signals.append("full_page_image")
    for signal in extra_signals:
        if signal not in SIGNALS:
            raise ValueError(f"Unknown route signal: {signal}")
        if signal not in signals:
            signals.append(signal)
    return {"locator": {"kind": "pdf_page", "value": str(physical_page), "bbox": None},
            "route": "visual" if signals else "text", "signals": signals, "rule_version": RULE_VERSION}
