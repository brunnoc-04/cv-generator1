from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"


def carregar_yaml(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)

def gerar_pdf(html_path: Path, pdf_path: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.pdf(path=str(pdf_path), format="A4", print_background=True,
                 margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"})
        browser.close()


def main():
    base = carregar_yaml(DATA_DIR / "base.yaml")
    pessoal = carregar_yaml(DATA_DIR / "pessoal.yaml")

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    template = env.get_template("cv.html")
    html = template.render(base=base, pessoal=pessoal)

    OUTPUT_DIR.mkdir(exist_ok=True)
    saida = OUTPUT_DIR / "cv.html"
    saida.write_text(html, encoding="utf-8")
    print(f"CV gerado em: {saida}")
    pdf = OUTPUT_DIR / "cv.pdf"
    gerar_pdf(saida, pdf)
    print(f"PDF gerado em: {pdf}")



if __name__ == "__main__":
    main()
