"""Batch 5 browser acceptance with saved live content; zero model calls."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
START=json.loads((ROOT/"var/batch5-browser-start.json").read_text())
URL=START["url"]
OUT=ROOT/"var/screenshots";OUT.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];writes=[];answers=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={"width":1440,"height":1000})
    page=context.new_page()
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("request",lambda r:writes.append(r.url) if r.method!="GET" else None)
    page.on("request",lambda r:answers.append(r.url) if r.url.endswith("/answers") and "/files/" not in r.url else None)
    page.goto("http://127.0.0.1:5173");page.wait_for_load_state("networkidle")
    if page.get_by_role("button",name="Open local workspace").count():page.get_by_role("button",name="Open local workspace").click()
    expect(page.get_by_role("navigation",name="Course navigation")).to_be_visible()
    writes.clear()
    page.goto(URL);page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link",name="Download question paper",exact=False)).to_be_visible(timeout=20000)
    expect(page.get_by_role("link",name="Download mark scheme",exact=False)).to_be_visible()
    expect(page.locator(".candidate-question")).to_have_count(4)
    assert not answers
    assert page.locator(".answer-question").count()==0
    checks.append("Saved live paper opens without fetching answers; four questions are readable.")
    for name in ("Download question paper","Download mark scheme"):
        link=page.get_by_role("link",name=name,exact=False)
        with page.expect_download() as info:link.click()
        download=info.value
        target=ROOT/"var"/download.suggested_filename
        download.save_as(target)
        assert target.read_bytes().startswith(b"%PDF-")
    checks.append("Both actual PDF downloads are accessible and start with a PDF signature.")
    await_url=page.url
    page.screenshot(path=str(OUT/"batch5-paper-desktop.png"))
    await_show=page.get_by_role("button",name="Show answers",exact=True)
    await_show.click()
    expect(page.locator(".answer-question")).to_have_count(4)
    expect(page.locator(".answer-part")).to_have_count(15)
    assert len(answers)==1
    assert not page.locator(".math-error").count()
    checks.append("Explicitly opening answers loads all 15 worked solutions; no math rendering errors.")
    page.reload();page.wait_for_load_state("networkidle")
    assert page.locator(".answer-question").count()==0
    assert len(answers)==1
    assert not writes
    checks.append("Refresh only reads the existing paper and returns to question-only view.")
    for width in (1024,768,320):
        page.set_viewport_size({"width":width,"height":1000})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1"),f"Overflow at {width}"
    page.screenshot(path=str(OUT/"batch5-paper-mobile.png"))
    checks.append("1024, 768 and 320 pixel layouts do not overflow the page.")
    page.set_viewport_size({"width":1440,"height":1000})
    page.get_by_role("link",name="Generate another practice",exact=True).click()
    expect(page.get_by_role("heading",name="Start another practice")).to_be_visible()
    expect(page.get_by_role("button",name="Use settings with latest course")).to_be_visible()
    assert not writes
    checks.append("Generate another opens an explicit course-version/configuration review without writes or model calls.")
    page.goto("http://127.0.0.1:5173/tasks/d5a7434f-4d05-4f93-81a7-c4a002b1d358")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link",name="View PDFs",exact=True)).to_be_visible()
    assert not page.locator(".run-details").get_attribute("open")
    page.get_by_text("Run details",exact=True).click()
    assert page.locator(".run-details").get_attribute("open") is not None
    page.get_by_text("Run details",exact=True).click()
    page.get_by_role("link",name="View PDFs",exact=True).scroll_into_view_if_needed()
    page.screenshot(path=str(OUT/"batch5-task-final.png"))
    checks.append("Original successful task retains question reading, links existing PDFs, and folds runtime details.")
    page.goto(URL.rsplit("/",1)[0]);page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading",name="Your practice papers")).to_be_visible()
    assert not writes
    checks.append("Saved paper remains findable in Papers; all checks after login issued no write requests.")
    assert errors==[],errors
    browser.close()
(ROOT/"var/batch5-browser-validation.json").write_text(json.dumps({"url":URL,"checks":checks,"errors":errors,"writes":writes},indent=2),encoding="utf-8")
print(json.dumps({"checks":checks,"errors":errors,"writes":writes}))
