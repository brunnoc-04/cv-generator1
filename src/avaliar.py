import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime

from ia import gerar, sugerir_resumo, ler, DATA, ROOT, VAGAS

def vaga_mais_recente():
    vagas = list(VAGAS.glob("*.txt"))
    if not vagas:
        sys.exit(f"❌ Nenhuma vaga .txt em {VAGAS}")
    return max(vagas, key=lambda p: p.stat().st_mtime)


REPORTS = ROOT / "reports"
EXECUCOES = REPORTS / "execucoes"
CV = DATA / "cv_vaga.yaml"
BACKUP = DATA / "cv_vaga.backup.yaml"


def rodar_testes() -> tuple[bool, list[str]]:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_cv_vaga.py",
         "-q", "--tb=no", "-rf", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    falhas = re.findall(r"^FAILED \S+::(.+?)(?: - |$)", r.stdout, re.M)
    return r.returncode == 0, falhas


def avaliar(n: int = 10, pausa: int = 5) -> dict:
    EXECUCOES.mkdir(parents=True, exist_ok=True)
    if CV.exists():
        shutil.copy(CV, BACKUP)

    aprovadas, contagem, detalhes = 0, Counter(), []

    try:
        for i in range(1, n + 1):
            print(f"\n▶ Execução {i}/{n}")
            try:
                gerar()
                passou, falhas = rodar_testes()
            except Exception as e:
                passou, falhas = False, [f"erro_geracao: {type(e).__name__}"]

            if CV.exists():
                shutil.copy(CV, EXECUCOES / f"run_{i:02d}.yaml")

            aprovadas += passou
            contagem.update(falhas)
            detalhes.append({"execucao": i, "passou": passou, "falhas": falhas})
            print("  ✅ PASSOU" if passou else f"  ❌ FALHOU: {falhas}")

            if i < n:
                time.sleep(pausa)  # evita estourar o limite de requisições da API
    finally:
        if BACKUP.exists():
            shutil.move(BACKUP, CV)

    taxa = aprovadas / n * 100
    relatorio = {
        "data": datetime.now().isoformat(timespec="seconds"),
        "execucoes": n,
        "aprovadas": aprovadas,
        "taxa_aprovacao": round(taxa, 1),
        "falhas_mais_comuns": contagem.most_common(),
        "detalhes": detalhes,
    }
    (REPORTS / "avaliacao.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    salvar_markdown(relatorio)

    print(f"\n📊 Taxa de aprovação: {taxa:.1f}% ({aprovadas}/{n})")
    for teste, qtd in contagem.most_common(5):
        print(f"   - {teste}: falhou {qtd}x")
    return relatorio


def salvar_markdown(r: dict) -> None:
    linhas = [
        "# Avaliação de confiabilidade da IA",
        "",
        f"- **Data:** {r['data']}",
        f"- **Execuções:** {r['execucoes']}",
        f"- **Taxa de aprovação:** {r['taxa_aprovacao']}% ({r['aprovadas']}/{r['execucoes']})",
        "",
        "## Testes que mais falharam",
        "",
        "| Teste | Falhas |",
        "|---|---|",
    ]
    linhas += [f"| `{t}` | {q} |" for t, q in r["falhas_mais_comuns"]] or ["| Nenhum | 0 |"]
    (REPORTS / "avaliacao.md").write_text("\n".join(linhas), encoding="utf-8")


if __name__ == "__main__":
    avaliar(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
