import os
import re
import sys
import shutil
import subprocess
import yaml
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VAGAS = DATA / "vagas"
OUTPUT = ROOT / "output"
HISTORICO = OUTPUT / "historico"
PDFS_VAGAS = OUTPUT / "vagas"
CV_VAGA = DATA / "cv_vaga.yaml"
BANCO = DATA / "resumos_aprovados.yaml"

load_dotenv(ROOT / ".env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

MIN_RESUMO = 300
MAX_RESUMO = 450
MAX_TENTATIVAS = 3
MAX_EXEMPLOS = 3  # quantos resumos aprovados vão como referência no prompt
NUMEROS_NAO_RESULTADO = {"285", "9"}  # carga horária e qtd. de projetos não contam como resultado

TERMOS_INFLADOS = [
    r"engenharia de qualidade", r"alta criticidade", r"escalabilidade",
    r"entregas? contínuas?", r"especializad[oa]s?", r"especialista",
    r"integraç(ão|ões) complexas?", r"soluç(ão|ões) críticas?",
    r"eficientes?", r"robust[oa]s?", r"garantir (a )?qualidade",
    r"s[óo]lid[oa]s? (experi[êe]ncia|conhecimento)",  # 🆕 perfil júnior
    r"(ampla|vasta) experi[êe]ncia",                   # 🆕
]

# 🆕 Técnicas de teste exigidas no resumo "manual" (palavra-chave de ATS)
TECNICAS_TESTE = [r"valor(es)? limite", r"classes? de equival[êe]ncia"]

# Termos que indicam que a vaga pede automação
TERMOS_AUTOMACAO = [
    r"automa[çc][ãa]o", r"automatiza", r"autom[áa]tic", r"scripts? de teste",
    r"playwright", r"selenium", r"cypress", r"robot framework", r"appium",
    r"pytest", r"jest", r"\be2e\b", r"ponta a ponta", r"\bbdd\b", r"cucumber",
    r"gherkin", r"ci/cd", r"pipeline", r"framework de testes?",
]

# Palavras da vaga que indicam qual resumo usar
SINAIS_RESUMO = {
    "automacao": TERMOS_AUTOMACAO + [r"python"],
    "api": [r"\bapi", r"postman", r"\brest\b", r"\bsql\b", r"banco de dados",
            r"backend", r"integra[çc]", r"endpoint"],
    "manual": [r"manual", r"explorat[óo]ri", r"funciona", r"regress[ãa]o",
               r"casos? de teste", r"cen[áa]rio"],
}

FRASES_OBRIGATORIAS = {
    "manual": "2 falhas críticas",
    "geral": "nyxcom",
}


# ---------- Utilidades ----------
def ler(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def salvar_yaml(caminho: Path, dados: dict):
    caminho.write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False, width=10_000),
        encoding="utf-8",
    )


def limpar(obj):
    """Remove quebras de linha, espaços extras e espaços duplos de todos os textos."""
    if isinstance(obj, str):
        return re.sub(r"\s+", " ", obj).strip()
    if isinstance(obj, list):
        return [limpar(i) for i in obj]
    if isinstance(obj, dict):
        return {k: limpar(v) for k, v in obj.items()}
    return obj


def numeros_de_resultado(texto: str) -> list[str]:
    return [
        n for n in re.findall(r"\d+", texto)
        if n not in NUMEROS_NAO_RESULTADO and not re.fullmatch(r"(19|20)\d{2}", n)
    ]


def contar(texto: str, padroes: list[str]) -> int:
    return sum(len(re.findall(p, texto)) for p in padroes)


def tem_termo_inflado(texto: str) -> bool:  # 🆕
    baixo = texto.lower()
    return any(re.search(t, baixo) for t in TERMOS_INFLADOS)


def vaga_pede_automacao(vaga: str) -> bool:
    return contar(vaga.lower(), TERMOS_AUTOMACAO) > 0


def escolher_vaga() -> Path:
    """Usa o arquivo passado no comando; senão, o .txt mais recente de data/vagas."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        caminho = Path(args[0])
        return caminho if caminho.is_absolute() else ROOT / caminho
    vagas = sorted(VAGAS.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not vagas:
        print(f"❌ Nenhuma vaga .txt encontrada em {VAGAS}")  # 🆕 sem traceback
        sys.exit(1)
    return vagas[0]


def validar_vaga(arquivo_vaga: Path):  # 🆕
    """Sai com mensagem amigável se o arquivo não existir, listando as vagas disponíveis."""
    if arquivo_vaga.exists():
        return
    print(f"❌ Arquivo não encontrado: {arquivo_vaga}")
    print("📂 Vagas disponíveis:")
    for v in sorted(VAGAS.glob("*.txt")):
        print(f"   - {v.relative_to(ROOT)}")
    sys.exit(1)


def confirmar_vaga(arquivo_vaga: Path, foco: str):  # 🆕
    """Confirma a vaga ANTES de chamar a IA (nada é alterado se cancelar)."""
    resp = input(f"❓ Gerar CV para '{arquivo_vaga.name}' (foco: {foco})? [Enter = sim | n = cancelar]: ")
    if resp.strip().lower() == "n":
        print("🚫 Cancelado. Nada foi alterado.")
        sys.exit(0)


def sugerir_resumo(vaga: str) -> str:
    texto = vaga.lower()
    pontos = {tipo: contar(texto, padroes) for tipo, padroes in SINAIS_RESUMO.items()}
    melhor = max(pontos, key=pontos.get)
    ordenados = sorted(pontos.values(), reverse=True)
    if ordenados[0] == 0 or ordenados[0] - ordenados[1] <= 1:
        return "geral"
    return melhor


def escolher_titulo(vaga: str, titulos: list[str]) -> str:
    """Usa o título do BASE que aparece na vaga; senão, o primeiro da lista."""
    texto = vaga.lower()
    for t in titulos:
        if t.lower() in texto:
            return t
    for t in titulos:  # tenta sem o "Júnior"
        if t.lower().replace(" júnior", "") in texto:
            return t
    return titulos[0]


def nome_da_vaga(arquivo_vaga: Path) -> str:
    """'2026-11-11_detsoft_qa' -> 'detsoft_qa'"""
    return re.sub(r"^\d{4}-\d{2}-\d{2}_", "", arquivo_vaga.stem)


def restaurar_textos(cv: dict, base: dict) -> dict:
    """Texto de bullets/projetos volta ao original; experiências ficam na ordem do BASE."""
    originais = {}
    for exp in base.get("experiencias", []):
        for b in exp.get("bullets", []):
            originais[b["id"]] = b["texto"]
    for p in base.get("projetos", []):
        originais[p["id"]] = p["texto"]
    originais = limpar(originais)

    for exp in cv.get("experiencias", []):
        for b in exp.get("bullets", []):
            if isinstance(b, dict) and b.get("id") in originais:
                b["texto"] = originais[b["id"]]
    for p in cv.get("projetos", []):
        if isinstance(p, dict) and p.get("id") in originais:
            p["texto"] = originais[p["id"]]

    ordem = [e["id"] for e in base.get("experiencias", [])]
    cv["experiencias"] = sorted(
        cv.get("experiencias", []),
        key=lambda e: ordem.index(e["id"]) if e.get("id") in ordem else len(ordem),
    )
    return cv


# ---------- Banco de resumos aprovados ----------
def carregar_banco() -> dict:
    if BANCO.exists():
        return yaml.safe_load(ler(BANCO)) or {}
    return {}


def salvar_aprovado(foco: str, texto: str, vaga_nome: str):
    banco = carregar_banco()
    lista = banco.setdefault(foco, [])
    if any(item["texto"] == texto for item in lista):
        return
    lista.append({"vaga": vaga_nome, "texto": texto})
    salvar_yaml(BANCO, banco)
    print(f"💾 Resumo aprovado salvo no banco ({foco}): {BANCO.name}")


def exemplos_aprovados(foco: str) -> str:
    # 🆕 ignora exemplos antigos com termos agora proibidos (ex.: "sólida experiência")
    lista = [i for i in carregar_banco().get(foco, []) if not tem_termo_inflado(i["texto"])]
    lista = lista[-MAX_EXEMPLOS:]
    if not lista:
        return ""
    itens = "\n".join(f"- {item['texto']}" for item in lista)
    return (
        "\nRESUMOS JÁ APROVADOS PELO CANDIDATO (referência de tom, estrutura e português; "
        "ADAPTE à vaga atual, não copie termos que esta vaga não pede):\n" + itens + "\n"
    )


# ---------- Prompt ----------
def montar_prompt(vaga: str, base: str, qa: str, foco: str, automacao: bool) -> str:
    regra_automacao = (
        "- A vaga PEDE AUTOMAÇÃO: TODOS os resumos devem citar Python E Playwright, "
        "ligados a um FATO do BASE (ex.: 'automatizei com Playwright a auditoria de catálogo "
        "e preços de uma loja real'). Nunca frases vagas como 'utilizo em meu desenvolvimento'."
        if automacao else ""
    )
    return f"""
Você adapta currículos de QA JÚNIOR para vagas específicas.

REGRAS OBRIGATÓRIAS:
- Use APENAS informações do BASE e das RESPOSTAS. Nunca invente ferramentas, empresas, datas, números ou experiências.
- Se a vaga pedir algo que o candidato não tem, NÃO inclua.
- PRESERVE todas as métricas e números (ex.: 2 falhas críticas, 95%, ~90%, 10x, 23 casos, R$ 140 mil → R$ 1 milhão, 285h).
- No resumo "manual", mantenha a frase com "2 falhas críticas".
- No resumo "manual", cite OBRIGATORIAMENTE o Jira e pelo menos uma técnica de teste (valor limite ou classes de equivalência).
- No resumo "geral", mantenha a menção à NyxCom.
- Escreva em primeira pessoa implícita ("Construo", "Identifiquei"), nunca em forma impessoal ("Construção").
- Escreva em português correto e natural. Releia cada frase: nada de palavras soltas ou sem sentido.

BULLETS E PROJETOS:
- NÃO reescreva o texto de bullets nem de projetos. Copie o "texto" EXATAMENTE como está no BASE.
- Mantenha o "id" de cada bullet, experiência e projeto.
- Você pode apenas REORDENAR bullets e projetos (mais ligados à vaga primeiro) e remover bullets irrelevantes sem métricas.

ADAPTAÇÃO À VAGA (ATS):
- O foco principal desta vaga é: "{foco}". Capriche mais nesse resumo.
- Nos RESUMOS, use os MESMOS TERMOS da vaga quando o candidato tiver aquela habilidade.
{regra_automacao}
- Ordene "skills" colocando primeiro as que a vaga pede e o candidato tem.

RESUMOS (MUITO IMPORTANTE):
- Os resumos do BASE são CURTOS DEMAIS. EXPANDA cada um.
- TODOS os 4 resumos (geral, automacao, api, manual) devem ter de 3 a 4 frases,
  entre {MIN_RESUMO} e {MAX_RESUMO} caracteres cada.
- Cada resumo deve combinar: ferramentas ligadas ao foco, a experiência como Analista de QA
  na NyxCom (2017–2021), a formação TripleTen (285h) e pelo menos 1 RESULTADO com número do BASE.
- "285h" e "9 projetos" NÃO contam como resultado. Use: 10x, 23 casos de teste, ~90%, 95%, 2 falhas críticas.
- Foco: "automacao" = Python, Playwright, Selenium, Pytest, POM; "api" = Postman, API REST, SQL, logs;
  "manual" = testes funcionais, exploratórios, regressão, Jira, valor limite, classes de equivalência; "geral" = visão equilibrada.
- Se mencionar IA, escreva "uso IA como apoio em pesquisa e aprendizado". Nunca "suporte de IA".
{exemplos_aprovados(foco)}
IDIOMAS:
- Copie a seção "idiomas" do BASE EXATAMENTE como está.

TOM:
- O candidato é JÚNIOR. Seja concreto e honesto, sem exagerar o nível.
- PROIBIDO: "engenharia de qualidade", "alta criticidade", "escalabilidade", "entrega(s) contínua(s)",
  "especializado", "especialista", "integrações complexas", "soluções críticas", "eficiente(s)",
  "robusto(s)", "garantir qualidade", "sólida experiência", "ampla experiência", "vasta experiência".
  Troque adjetivos por FATOS (ex.: "experiência prática em...").

Responda SOMENTE com YAML válido, com exatamente as mesmas chaves do BASE.

=== VAGA ===
{vaga}

=== BASE (estrutura e dados reais) ===
{base}

=== RESPOSTAS DO CANDIDATO ===
{qa}
"""


# ---------- IA ----------
def chamar_ia_texto(prompt: str, temperatura: float = 0.2) -> str:
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperatura),
    )
    return resp.text.strip()


def chamar_ia(prompt: str) -> dict:
    texto = chamar_ia_texto(prompt).removeprefix("```yaml").removesuffix("```").strip()
    return limpar(yaml.safe_load(texto))


def problemas_resumo(cv: dict, automacao: bool) -> list[str]:
    erros = []
    for chave, texto in cv.get("resumos", {}).items():
        n = len(texto)
        baixo = texto.lower()
        if n < MIN_RESUMO:
            erros.append(f'- Resumo "{chave}" tem {n} caracteres. Expanda para {MIN_RESUMO}-{MAX_RESUMO}.')
        elif n > MAX_RESUMO + 100:
            erros.append(f'- Resumo "{chave}" tem {n} caracteres. Reduza para {MIN_RESUMO}-{MAX_RESUMO}.')
        if not numeros_de_resultado(texto):
            erros.append(f'- Resumo "{chave}" sem resultado numérico real (285h e 9 projetos não contam). Use 10x, 23 casos, ~90%...')
        if automacao and not ("playwright" in baixo and "python" in baixo):
            erros.append(f'- Resumo "{chave}" não cita Python e Playwright, mas a vaga pede automação.')
        frase = FRASES_OBRIGATORIAS.get(chave)
        if frase and frase not in baixo:
            erros.append(f'- Resumo "{chave}" precisa conter EXATAMENTE "{frase}" (verifique a ortografia).')
        if chave == "manual":  # 🆕 palavras-chave de ATS
            if "jira" not in baixo:
                erros.append('- Resumo "manual" precisa citar o Jira.')
            if not any(re.search(t, baixo) for t in TECNICAS_TESTE):
                erros.append('- Resumo "manual" precisa citar uma técnica: valor limite ou classes de equivalência.')

    texto_total = yaml.safe_dump(cv, allow_unicode=True, width=10_000).lower()
    for termo in TERMOS_INFLADOS:
        achado = re.search(termo, texto_total)
        if achado:
            erros.append(f'- Termo proibido encontrado: "{achado.group()}". Reescreva com um fato concreto.')
    return erros


def gerar(arquivo_vaga: Path, foco: str) -> dict:
    vaga = ler(arquivo_vaga)
    automacao = vaga_pede_automacao(vaga)
    print(f"🤖 Vaga pede automação: {'sim' if automacao else 'não'}")

    base_txt = ler(DATA / "base.yaml")
    base = yaml.safe_load(base_txt)
    prompt_original = montar_prompt(vaga, base_txt, ler(DATA / "qa.yaml"), foco, automacao)

    prompt = prompt_original
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        cv = restaurar_textos(chamar_ia(prompt), base)

        faltando = set(base.keys()) - set(cv.keys())
        if faltando:
            raise ValueError(f"YAML gerado sem as chaves: {faltando}")

        erros = problemas_resumo(cv, automacao)
        if not erros:
            break

        print(f"Tentativa {tentativa}: {len(erros)} problema(s) encontrado(s), pedindo correção...")
        for e in erros:
            print(f"   {e}")
        prompt = (
            prompt_original
            + "\n\n=== SUA RESPOSTA ANTERIOR ===\n"
            + yaml.safe_dump(cv, allow_unicode=True, sort_keys=False)
            + "\n=== CORRIJA ESTES PROBLEMAS E DEVOLVA O YAML COMPLETO ===\n"
            + "\n".join(erros)
        )
    else:
        print("⚠️ Limite de tentativas atingido; salvando a última versão.")

    # Título definido pelo Python, não pela IA
    titulo = escolher_titulo(vaga, base["titulos"])
    cv["titulos"] = [titulo] + [t for t in base["titulos"] if t != titulo]
    print(f"🏷️ Título: {titulo}")

    salvar_yaml(CV_VAGA, cv)
    print(f"CV adaptado salvo em: {CV_VAGA}")
    return cv


# ---------- Revisão humana do resumo ----------
def regerar_resumo(arquivo_vaga: Path, foco: str):
    """Pede à IA um resumo NOVO só para o foco atual. O resto do CV não muda."""
    vaga = ler(arquivo_vaga)
    automacao = vaga_pede_automacao(vaga)
    cv = yaml.safe_load(ler(CV_VAGA))
    atual = cv["resumos"][foco]

    regra_auto = "- Cite Python E Playwright ligados a um fato do BASE." if automacao else ""
    obrigatoria = FRASES_OBRIGATORIAS.get(foco)
    regra_frase = f'- Contenha EXATAMENTE "{obrigatoria}".' if obrigatoria else ""
    regra_manual = (  # 🆕
        "- Cite o Jira e pelo menos uma técnica (valor limite ou classes de equivalência)."
        if foco == "manual" else ""
    )

    prompt_base = f"""
Reescreva o resumo profissional "{foco}" de um QA JÚNIOR para a vaga abaixo.
O candidato REJEITOU esta versão: "{atual}". Faça uma versão DIFERENTE e melhor.

REGRAS:
- 3 a 4 frases, entre {MIN_RESUMO} e {MAX_RESUMO} caracteres, português correto e natural.
- Use só fatos do BASE. Inclua a NyxCom (2017–2021), a TripleTen (285h) e 1 resultado numérico
  (10x, 23 casos de teste, ~90%, 95%, 2 falhas críticas).
- Use os mesmos termos da vaga quando o candidato tiver a habilidade.
{regra_auto}
{regra_frase}
{regra_manual}
- Sem: especialista, robusto, eficiente, garantir qualidade, escalabilidade, sólida/ampla/vasta experiência.
{exemplos_aprovados(foco)}
Responda SOMENTE com o texto do resumo, sem aspas e sem markdown.

=== VAGA ===
{vaga}

=== BASE ===
{ler(DATA / "base.yaml")}
"""
    prompt = prompt_base
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        texto = limpar(chamar_ia_texto(prompt, temperatura=0.7).strip('"'))
        erros = problemas_resumo({"resumos": {foco: texto}}, automacao)
        if not erros:
            break
        print(f"   Tentativa {tentativa}: corrigindo {len(erros)} problema(s)...")
        prompt = prompt_base + f"\n\nSUA RESPOSTA ANTERIOR:\n{texto}\n\nCORRIJA:\n" + "\n".join(erros)

    cv["resumos"][foco] = texto
    salvar_yaml(CV_VAGA, cv)


def revisar_resumo(arquivo_vaga: Path, foco: str):
    """Mostra o resumo e só libera o PDF depois da aprovação."""
    automacao = vaga_pede_automacao(ler(arquivo_vaga))
    while True:
        try:
            cv = yaml.safe_load(ler(CV_VAGA))
        except yaml.YAMLError:
            input("❌ O YAML ficou inválido após a edição. [Enter] para reabrir e corrigir...")
            subprocess.run(["notepad", str(CV_VAGA)])
            continue

        texto = limpar(cv["resumos"][foco])
        print("\n" + "=" * 70)
        print(f"📝 RESUMO ({foco}) — {len(texto)} caracteres:\n")
        print(texto)
        print("=" * 70)

        avisos = problemas_resumo({"resumos": {foco: texto}}, automacao)
        for a in avisos:
            print(f"⚠️ {a}")

        op = input("[Enter] aprovar | [e] editar | [r] regerar resumo: ").strip().lower()
        if op == "":
            cv["resumos"][foco] = texto
            salvar_yaml(CV_VAGA, cv)
            salvar_aprovado(foco, texto, nome_da_vaga(arquivo_vaga))
            return
        if op == "e":
            print(f"✏️ Edite 'resumos' > '{foco}', salve (Ctrl+S) e FECHE o Bloco de Notas...")
            subprocess.run(["notepad", str(CV_VAGA)])  # o script espera você fechar
        elif op == "r":
            print("🔄 Gerando um novo resumo...")
            regerar_resumo(arquivo_vaga, foco)
        else:
            print("Opção inválida.")


# ---------- Pipeline completo ----------
def main():
    arquivo_vaga = escolher_vaga()
    validar_vaga(arquivo_vaga)  # 🆕 antes de qualquer leitura
    foco = sugerir_resumo(ler(arquivo_vaga))
    so_pdf = "--so-pdf" in sys.argv
    print(f"📄 Vaga: {arquivo_vaga.name}")
    print(f"🎯 Resumo recomendado: {foco}")

    if so_pdf:
        print("✏️ Modo --so-pdf: usando o cv_vaga.yaml atual (sem gerar com IA).")
    else:
        confirmar_vaga(arquivo_vaga, foco)  # 🆕 antes de gastar chamada de IA
        gerar(arquivo_vaga, foco)

    revisar_resumo(arquivo_vaga, foco)

    print("🧪 Rodando testes de qualidade do CV...")
    testes = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], cwd=ROOT)
    if testes.returncode != 0:
        print("❌ Testes falharam. PDF NÃO gerado. Revise o cv_vaga.yaml e rode com --so-pdf.")
        sys.exit(1)

    subprocess.run([sys.executable, str(ROOT / "src" / "pdf.py"), "--resumo", foco], cwd=ROOT, check=True)

    PDFS_VAGAS.mkdir(parents=True, exist_ok=True)
    pdf_final = PDFS_VAGAS / f"cv_{nome_da_vaga(arquivo_vaga)}.pdf"
    shutil.move(OUTPUT / f"cv_{foco}.pdf", pdf_final)
    print(f"✅ PDF da vaga: {pdf_final}")

    HISTORICO.mkdir(parents=True, exist_ok=True)
    shutil.copy(CV_VAGA, HISTORICO / f"{arquivo_vaga.stem}.yaml")
    print(f"🗂️ Histórico salvo em: {HISTORICO / (arquivo_vaga.stem + '.yaml')}")


if __name__ == "__main__":
    main()
