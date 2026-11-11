import argparse
import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
OUTPUT = ROOT / "output"


def carregar_cv() -> tuple[dict, dict]:
    cv = yaml.safe_load((DATA / "cv_vaga.yaml").read_text(encoding="utf-8"))
    pessoal = yaml.safe_load((DATA / "pessoal.yaml").read_text(encoding="utf-8"))
    return cv, pessoal


def renderizar_html(cv: dict, pessoal: dict, resumo: str) -> str:
    if resumo not in cv["resumos"]:
        raise ValueError(f"Resumo '{resumo}' não existe. Opções: {list(cv['resumos'])}")
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    return env.get_template("cv.html").render(
        cv=cv,
        p=pessoal,
        resumo=cv["resumos"][resumo],
        projetos_primeiro=resumo in ("automacao", "api"),
    )


def gerar_pdf(resumo: str = "geral") -> Path:
    cv, pessoal = carregar_cv()
    html = renderizar_html(cv, pessoal, resumo)
    OUTPUT.mkdir(exist_ok=True)

    (OUTPUT / "cv_preview.html").write_text(html, encoding="utf-8")
    saida = OUTPUT / f"cv_{resumo}.pdf"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(saida),
            format="A4",
            print_background=True,
            margin={"top": "12mm", "bottom": "12mm", "left": "14mm", "right": "14mm"},
        )
        browser.close()

    print(f"PDF salvo em: {saida}")
    return saida


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera o CV em PDF")
    parser.add_argument("--resumo", default="geral", help="geral | automacao | api | manual")
    gerar_pdf(parser.parse_args().resumo)
