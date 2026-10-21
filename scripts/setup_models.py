"""Download local parser weights only; never reads or uploads course documents."""
from pathlib import Path
from docling.utils.model_downloader import download_models

target = Path(__file__).resolve().parents[1] / "var/models"
download_models(output_dir=target, with_layout=True, with_tableformer=True,
                with_code_formula=False, with_picture_classifier=False, with_rapidocr=False)
print("Local Docling weights ready:", target)
