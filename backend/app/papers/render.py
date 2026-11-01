"""Offline trusted HTML templates. No generated code or remote assets execute."""
import base64
import html
import io
import re
from pathlib import Path
from django.conf import settings
from pypdf import PdfReader
from playwright.sync_api import sync_playwright
from app.core.errors import DomainError

RENDERER_VERSION = "chromium-katex-v5"


def escaped(value):
    return html.escape(str(value), quote=True)


def reflow_math(latex):
    """Break only explicit top-level wide spacing; preserve groups and environments."""
    depth = environments = fences = 0
    rows = []
    start = index = 0
    while index < len(latex):
        if latex.startswith(r"\begin{", index):
            environments += 1
        elif latex.startswith(r"\end{", index):
            environments = max(0, environments - 1)
        elif latex.startswith(r"\left", index):
            fences += 1
        elif latex.startswith(r"\right", index):
            fences = max(0, fences - 1)
        if latex.startswith(r"\qquad", index) and depth == environments == fences == 0:
            rows.append(latex[start:index])
            index += len(r"\qquad")
            start = index
            continue
        if latex[index] == "{" and (index == 0 or latex[index-1] != "\\"):
            depth += 1
        elif latex[index] == "}" and (index == 0 or latex[index-1] != "\\"):
            depth = max(0, depth - 1)
        index += 1
    if not rows:
        return latex
    rows.append(latex[start:])
    return r"\begin{gathered}" + r" \\ ".join(rows) + r"\end{gathered}"


def blocks_html(blocks, assets):
    result = []
    for block in blocks:
        kind = block["type"]
        if kind == "text":
            result.append(f'<p>{escaped(block["text"])}</p>')
        elif kind == "math":
            display = "true" if block.get("display") else "false"
            result.append(f'<div class="formula" data-display="{display}" data-latex="{escaped(block["latex"])}" data-reflow="{escaped(reflow_math(block["latex"]))}"></div>')
        elif kind == "table":
            columns = "".join(f"<th>{escaped(v)}</th>" for v in block["columns"])
            rows = "".join("<tr>" + "".join(f"<td>{escaped(v)}</td>" for v in row) + "</tr>" for row in block["rows"])
            result.append(f'<table><caption>{escaped(block.get("caption",""))}</caption><thead><tr>{columns}</tr></thead><tbody>{rows}</tbody></table>')
        elif kind == "asset_ref":
            asset = assets.get(block["asset_id"])
            if not asset:
                raise DomainError("PDF_ASSET_MISSING", "A required diagram is missing.", retryable=False)
            # Image context isolates SVG from the document; external requests are also blocked.
            data = base64.b64encode(asset["svg"].encode()).decode()
            result.append(f'<figure><img src="data:image/svg+xml;base64,{data}" alt="{escaped(asset["alt"])}"><figcaption>{escaped(asset["alt"])}</figcaption></figure>')
        else:
            raise DomainError("PDF_BLOCK_UNSUPPORTED", "This content block cannot be printed.", retryable=False)
    return "".join(result)


def document_html(content, kind):
    m = content.payload["metadata"]
    payload = content.payload["content"]
    assets = {a["id"]: a for a in payload["assets"]}
    answers = kind == "answers"
    title = "Mark scheme" if answers else "Question paper"
    plan = m["blueprint"]
    banner = "Synthetic fixture - not a real model result" if m["mode"] == "fixture" else "AI-generated practice"
    parts = [f'<header><p class="eyebrow">{escaped(m["course_code"])} / {escaped(m["course_title"])}</p><h1>{title}</h1>',
        f'<p>{escaped(m["config"]["difficulty"].replace("_"," ").title())} / {len(payload["pairs"])} main questions / {sum(len(p["parts"]) for p in payload["pairs"])} subquestions</p>',
        f'<p>{escaped(plan["attempt_marks"])} attempt marks / {escaped(plan["suggested_minutes"])} suggested minutes</p>',
        f'<p class="small">{banner}. Difficulty and timing are not calibrated to an official exam.</p>',
        f'<p class="small">Content version: {content.id}<br>Course version: {escaped(m["course_version_number"])}</p></header>']
    if answers:
        parts.append('<p class="notice">Suggested marking guidance. This is not an official mark scheme.</p>')
    else:
        for section in plan.get("sections", []):
            selection = section["selection"]
            rule = "Answer all questions" if selection["mode"] == "all" else f'Answer {selection["choose_count"]} questions'
            numbers = [str(i+1) for i,p in enumerate(payload["pairs"]) if p["question_id"] in section["question_ids"]]
            parts.append(f'<p class="notice">{escaped(section["title"])}: {escaped(rule)} ({", ".join(numbers)}).</p>')
    for index, pair in enumerate(payload["pairs"]):
        marks = sum(p["marks"] for p in pair["parts"])
        parts.append(f'<article class="question"><h2>Question {index+1}<span>{marks:g} marks</span></h2>')
        if not answers:
            parts.append(blocks_html(pair["stem"], assets))
            for n, part in enumerate(pair["parts"]):
                parts.append(f'<section class="part"><h3>({chr(97+n)})<span>{part["marks"]:g} marks</span></h3>')
                parts.append(blocks_html(part["prompt"], assets))
                if part.get("assumptions"):
                    parts.append(f'<p class="small">{escaped("; ".join(part["assumptions"]))}</p>')
                parts.append("</section>")
        else:
            for n, answer in enumerate(pair["answers"]):
                parts.append(f'<section class="part"><h3>Question {index+1} ({chr(97+n)}) Worked solution</h3>')
                parts.append(blocks_html(answer["worked_solution"], assets))
                parts.append('<div class="marking"><h4>Final answer</h4>' + blocks_html(answer["final_answer"], assets))
                parts.append("<h4>Marking points</h4><ul>")
                for point in answer["marking_points"]:
                    alternative = f' / alternative group: {escaped(point["alternative_group"])} (count once)' if point.get("alternative_group") else ""
                    parts.append(f'<li>{escaped(point["text"])} <strong>{point["marks"]:g} marks</strong>{alternative}</li>')
                parts.append("</ul>")
                if answer.get("acceptable_alternatives"):
                    parts.append(f'<p>Acceptable alternatives: {escaped("; ".join(answer["acceptable_alternatives"]))}</p>')
                if answer.get("units"): parts.append(f'<p>Units: {escaped(answer["units"])}</p>')
                if answer.get("precision"): parts.append(f'<p>Precision: {escaped(answer["precision"])}</p>')
                parts.append("</div></section>")
        parts.append("</article>")
    css = (Path(__file__).parent / "templates/print.css").read_text(encoding="utf-8")
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>{css}</style></head><body class="{kind}">{"".join(parts)}</body></html>'


def render_pdf(content, kind):
    assets = settings.BASE_DIR / "frontend/node_modules/katex/dist"
    if not (assets / "katex.min.js").is_file():
        raise DomainError("PDF_RUNTIME_MISSING", "The local math renderer is missing. Install the locked frontend dependencies.", retryable=True)
    css = (assets / "katex.min.css").read_text(encoding="utf-8")
    def font_url(match):
        name = match.group(1).strip("'\"")
        path = (assets / name).resolve()
        if not path.is_relative_to(assets.resolve()) or not path.is_file():
            raise DomainError("PDF_FONT_MISSING", "A required local math font is missing.")
        encoded = base64.b64encode(path.read_bytes()).decode()
        suffix = path.suffix.lstrip(".")
        return f"url(data:font/{suffix};base64,{encoded})"
    css = re.sub(r"url\(([^)]+)\)", font_url, css)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 658, "height": 1123})
            page.set_default_timeout(15000)
            page.route("**/*", lambda route: route.abort())
            page.set_content(document_html(content, kind), wait_until="load")
            page.add_style_tag(content=css)
            page.add_script_tag(path=str(assets / "katex.min.js"))
            page.evaluate("""() => {
                for (const el of document.querySelectorAll('[data-latex]')) {
                    katex.render(el.dataset.latex, el, {displayMode:el.dataset.display==='true',
                        throwOnError:true,trust:false,strict:'warn',maxExpand:1000,maxSize:20});
                }
            }""")
            page.evaluate("async () => {await document.fonts.ready; await Promise.all([...document.images].map(i=>i.decode()));}")
            # Fit long equations only within a readable floor; otherwise fail visibly.
            page.evaluate("""() => {
                for (const el of document.querySelectorAll('.formula')) {
                    if(el.scrollWidth > el.clientWidth && el.dataset.reflow!==el.dataset.latex) {
                        katex.render(el.dataset.reflow, el, {displayMode:true,throwOnError:true,trust:false,
                            strict:'warn',maxExpand:1000,maxSize:20});
                    }
                    if(el.scrollWidth > el.clientWidth) {
                        const ratio=el.clientWidth/el.scrollWidth;
                        if(ratio < .75) throw new Error('Formula exceeds readable printable width');
                        el.style.fontSize=(parseFloat(getComputedStyle(el).fontSize)*ratio)+'px';
                    }
                }
            }""")
            page.evaluate("async () => await document.fonts.ready")
            footer = f'<div style="font-size:8px;width:100%;margin:0 18mm;color:#555;display:flex;justify-content:space-between"><span>{escaped("Question paper" if kind=="questions" else "Mark scheme")} / {str(content.id)[:8]}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
            data = page.pdf(format="A4", print_background=True, display_header_footer=True, header_template="<span></span>",
                footer_template=footer, margin={"top":"18mm","bottom":"18mm","left":"18mm","right":"18mm"}, prefer_css_page_size=True)
        finally:
            browser.close()
    reader = PdfReader(io.BytesIO(data))
    if not reader.pages or not data.startswith(b"%PDF-"):
        raise DomainError("PDF_INVALID", "The renderer returned an invalid PDF.")
    return data, len(reader.pages)
