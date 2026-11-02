"""Read-only check of the real material library. No model calls or course edits."""
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/"var/batch6/legacy-topic-mapping.json").read_text())
OUT=ROOT/"var/screenshots";OUT.mkdir(exist_ok=True)
BASE="http://127.0.0.1:5173"
checks=[];errors=[];writes=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True)
 page=browser.new_page(viewport={"width":1440,"height":1000})
 page.on("pageerror",lambda e:errors.append(str(e)))
 page.goto(BASE);page.wait_for_load_state("networkidle")
 page.get_by_role("button",name="Open local workspace").click()
 expect(page.get_by_role("navigation",name="Course navigation")).to_be_visible()
 page.on("request",lambda r:writes.append(r.url) if r.method!="GET" else None)
 page.goto(f"{BASE}/courses/{data['course_id']}/materials");page.wait_for_load_state("networkidle")
 expect(page.locator(".material-row")).to_have_count(11)
 page.get_by_role("navigation",name="Material topics").get_by_role("button",name="Topic 2",exact=False).click()
 expect(page.locator(".material-row")).to_have_count(5)
 page.get_by_label("Include course-wide materials").click()
 expect(page.get_by_label("Include course-wide materials")).to_be_checked()
 expect(page.locator(".material-row")).to_have_count(11)
 page.get_by_label("Include course-wide materials").click()
 expect(page.get_by_label("Include course-wide materials")).not_to_be_checked()
 page.get_by_role("textbox",name="Search materials").fill("summary")
 expect(page.locator(".material-row")).to_have_count(1)
 filters=page.url
 page.get_by_role("button",name="View source:",exact=False).click()
 expect(page.get_by_role("button",name="Close source")).to_be_visible()
 page.get_by_role("button",name="Next page",exact=True).click()
 expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("2")
 assert parse_qs(urlparse(page.url).query)["topic"]==[data["topic_id"]]
 page.reload();page.wait_for_load_state("networkidle")
 expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("2")
 page.get_by_role("button",name="Close source").click()
 assert page.url==filters
 page.go_back()
 expect(page.get_by_role("spinbutton",name="PDF page")).to_have_value("2")
 page.go_forward()
 expect(page.get_by_role("button",name="Close source")).to_have_count(0)
 expect(page.locator(".material-row")).to_have_count(1)
 checks.append("Topic/shared filters, search and source version/page persist through refresh and close.")
 page.get_by_role("button",name="Clear filters").click()
 expect(page.locator(".material-row")).to_have_count(5)
 page.get_by_role("button",name="Manage topics").first.click()
 expect(page.get_by_role("heading",name="Manage topic links")).to_be_visible()
 page.get_by_role("button",name="Cancel",exact=True).click()
 assert not page.locator(".processing-activity").get_attribute("open")
 for width in (1440,1024,768,320):
  page.set_viewport_size({"width":width,"height":1000})
  page.wait_for_timeout(150)
  assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1"),f"Overflow at {width}"
  page.screenshot(path=str(OUT/f"batch6-materials-{width}.png"))
 assert not writes,writes
 assert not errors,errors
 checks.append("Four responsive sizes, link editor, collapsed processing history; no writes or JS errors.")
 browser.close()
(ROOT/"var/batch6/materials-browser.json").write_text(json.dumps({"checks":checks,"errors":errors,"writes":writes},indent=2))
print(json.dumps({"passed":len(checks),"checks":checks}))
