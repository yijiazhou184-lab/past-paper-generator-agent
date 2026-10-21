"""Download the official EDB Windows archive into the ignored project runtime."""
import hashlib
import json
import re
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".runtime"
target.mkdir(exist_ok=True)
page = urllib.request.urlopen(
    "https://www.enterprisedb.com/download-postgresql-binaries", timeout=30
).read().decode()
urls = sorted(set(re.findall(r'https://[^\s"<>]+windows[^\s"<>]+zip', page)))
candidates = [url for url in urls if "postgresql-17." in url and "x64" in url]
linked = re.search(r'Version <!-- -->(17\.\d+).*?href="(https://sbp\.enterprisedb\.com/[^"]+)"[^>]*><img alt="Windows x86-64"', page)
if not candidates and not linked:
    print(json.dumps({"discovered_downloads": urls}))
    raise SystemExit("No PostgreSQL 17 archive found; inspect official download page.")
url = linked.group(2) if linked else sorted(candidates, key=lambda u: tuple(map(int, re.search(r"17\.(\d+)-(\d+)", u).groups())))[-1]
archive = target / "postgresql.zip"
print("Downloading", url, flush=True)
urllib.request.urlretrieve(url, archive)
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        resolved = (target / name).resolve()
        if not resolved.is_relative_to(target.resolve()):
            raise ValueError("Unsafe archive path")
    z.extractall(target)
(target / "postgres-download.json").write_text(json.dumps({
    "url": url, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()
}, indent=2))
print("PostgreSQL extracted", flush=True)
