"""
Mede a confiabilidade da IA: gera o CV N vezes para a mesma vaga,
roda o pytest em cada geração e calcula a taxa de aprovação.
NÃO é necessário para gerar CVs no dia a dia (para isso, use o ia.py).
"""
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime

from ia import gerar, sugerir_resumo, ler, DATA, ROOT, VAGAS

CV = DATA / "cv_vaga.yaml"
BACKUP = DATA / "cv_vaga.backup.yaml"
REPORTS = ROOT / "reports"
EXECUCOES = REPORTS / "execucoes"


def vaga_mais_recente():
    vagas = list(VAGAS.glob("*.txt"))
    if not vagas:
        sys.exit(f"❌ Nenhuma vaga .txt em {VAGAS}")
    return max(vagas, key=lambda p: p.stat().st_mtime)


def rodar_testes():
    """Roda o pytest e devolve (passou, lista_de_testes_que_falharam)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q", "-rf", "--no-header"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )
    falhas = [
        linha.split("::", 1)[-1].split(" - ")[0].strip()
        for linha in r.stdout.splitlines()
        if linha.startswith("FAILED")
    ]
    return r.returncode == 0, falhas


def salvar_relatorio(relatorio: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "avaliacao.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    linhas = [
        "# Avaliação de confiabilidade da IA",
        "",
        f"- **Data:** {relatorio['data']}",
        f"- **Vaga:** {relatorio['vaga']}",
        f"- **Foco:** {relatorio['foco']}",
        f"- **Execuções:** {relatorio['execucoes']}",
        f"- **Taxa de aprovação:** {relatorio['taxa']}% "
        f"({relatorio['aprovadas']}/{relatorio['execucoes']})",
        "",
        "## Testes que mais falharam",
        "",
        "| Teste | Falhas |",
        "|---|---|",
    ]
    if relatorio["mais_falharam"]:
        linhas += [f"| {t} | {n} |" for t, n in relatorio["mais_falharam"]]
    else:
        linhas.append("| Nenhum | 0 |")
    (REPORTS / "avaliacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def avaliar(n: int = 10, pausa: int = 5) -> dict:
    vaga = vaga_mais_recente()
    foco = sugerir_resumo(ler(vaga))
    print(f"📄 Avaliando: {vaga.name} (foco: {foco})")

    EXECUCOES.mkdir(parents=True, exist_ok=True)
    if CV.exists():
        shutil.copy(CV, BACKUP)  # protege o seu CV atual

    aprovadas, contagem, detalhes = 0, Counter(), []
    try:
        for i in range(1, n + 1):
            print(f"\n▶ Execução {i}/{n}")
            try:
                gerar(vaga, foco)
                passou, falhas = rodar_testes()
            except Exception as e:
                passou, falhas = False, [f"erro_geracao: {type(e).__name__}: {e}"]

            if passou:
                aprovadas += 1
                print("  ✅ PASSOU")
            else:
                print(f"  ❌ FALHOU: {falhas}")
                contagem.update(falhas)

            if CV.exists():
                shutil.copy(CV, EXECUCOES / f"execucao_{i:02d}.yaml")
            detalhes.append({"execucao": i, "passou": passou, "falhas": falhas})

            if i < n:
                time.sleep(pausa)  # evita limite de requisições do Gemini
    finally:
        if BACKUP.exists():
            shutil.copy(BACKUP, CV)  # devolve o seu CV original

    relatorio = {
        "data": datetime.now().isoformat(timespec="seconds"),
        "vaga": vaga.name,
        "foco": foco,
        "execucoes": n,
        "aprovadas": aprovadas,
        "taxa": round(aprovadas / n * 100, 1),
        "mais_falharam": contagem.most_common(10),
        "detalhes": detalhes,
    }
    salvar_relatorio(relatorio)

    print(f"\n📊 Taxa de aprovação: {relatorio['taxa']}% ({aprovadas}/{n})")
    for teste, qtd in relatorio["mais_falharam"]:
        print(f"   - {teste}: falhou {qtd}x")
    return relatorio


if __name__ == "__main__":
    avaliar(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
