import copy
import io
from pathlib import Path
import pytest
from pypdf import PdfReader
from app.papers.render import render_pdf, document_html
from app.core.errors import DomainError
from test_papers import paper
from test_generation_snapshot import version, config, planned
from test_course_analysis import course_payload, analysis_context
from test_course_drafts import draft


def test_actual_chromium_renders_long_table_graph_and_math(paper, tmp_path):
    content = copy.copy(paper.content)
    content.payload = copy.deepcopy(content.payload)
    pairs = content.payload["content"]["pairs"]
    pairs[0]["answers"][0]["worked_solution"].append({"type":"text","text":"ANSWER-ONLY-SENTINEL"})
    pairs[0]["answers"][0]["worked_solution"].append({"type":"math","latex":r"g(x)=x^2;\qquad x=1:\ \text{neither local maximum nor local minimum};\qquad x=3:\ \text{strict local maximum}.","display":True})
    pairs[0]["stem"].extend([
        {"type":"math","latex":r"f(x)=\begin{cases}x^2&x<0\\\sqrt{x+1}&x\ge0\end{cases}","display":True},
        {"type":"table","columns":["Observation","Value"],"rows":[[f"ROW-{i:03}",str(i*i)] for i in range(80)],"caption":"Synthetic long table"},
        {"type":"asset_ref","asset_id":"test-graph"}])
    content.payload["content"]["assets"].append({"id":"test-graph","svg":'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><path d="M20 180L380 180M30 190L30 10" fill="none" stroke="black"/><path d="M30 160Q180 160 340 20" fill="none" stroke="blue"/></svg>',"alt":"Synthetic curve layout fixture"})
    output={}
    for kind in ("questions","answers"):
        data,pages=render_pdf(content,kind)
        assert pages>0
        output[kind]=" ".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
        (tmp_path/f"{kind}.pdf").write_bytes(data)
    assert "ANSWER-ONLY-SENTINEL" not in output["questions"]
    assert "ANSWER-ONLY-SENTINEL" in output["answers"]
    assert "ROW-079" in output["questions"]
    assert "Synthetic curve layout fixture" in output["questions"]
    assert str(content.id) in output["questions"] and str(content.id) in output["answers"]


def test_unsupported_formula_and_missing_asset_fail_visibly(paper):
    content=copy.copy(paper.content)
    content.payload=copy.deepcopy(content.payload)
    content.payload["content"]["pairs"][0]["stem"]=[{"type":"asset_ref","asset_id":"missing"}]
    with pytest.raises(DomainError,match="PDF_ASSET_MISSING"):
        document_html(content,"questions")
    content.payload["content"]["pairs"][0]["stem"]=[{"type":"math","latex":r"\definitelyNotSupported{1}","display":True}]
    with pytest.raises(Exception,match="Undefined control sequence"):
        render_pdf(content,"questions")
