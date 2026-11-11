from playwright.sync_api import sync_playwright

html = "<h1>Brunno - Analista de QA</h1><p>Setup funcionando!</p>"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content(html)
    from pathlib import Path

    RAIZ = Path(__file__).resolve().parent.parent
    page.pdf(path=RAIZ / "output" / "teste.pdf", format="A4")

    browser.close()

print("PDF gerado em output/teste.pdf ✅")
