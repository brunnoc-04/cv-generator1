import re
import yaml
import pytest
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

PROIBIDAS = ["cypress", "robot framework", "jmeter", "appium", "jenkins"]

# Regex: pega plural e variações. Inclui adjetivos vazios (sem prova).
TERMOS_INFLADOS = [
    r"engenharia de qualidade",
    r"alta criticidade",
    r"escalabilidade",
    r"entregas? contínuas?",
    r"especializad[oa]s?",
    r"especialista",
    r"integraç(ão|ões) complexas?",
    r"soluç(ão|ões) críticas?",
    r"eficientes?",
    r"robust[oa]s?",
    r"garantir (a )?qualidade",
    r"base s[óo]lida",
    r"s[óo]lid[oa]s?",
    r"(ampla|vasta) experi[êe]ncia",
]

METRICAS_OBRIGATORIAS = ["285h", "~90%", "23 casos", "10x"]

TIPOS_RESUMO = ["geral", "automacao", "api", "manual"]

# Fatos atribuídos à empresa errada (ex.: integrações "na NyxCom")
ATRIBUICOES_ERRADAS = [
    r"(integraç\w+|bling|\bsgi\b|marketplaces?)[^.]{0,40}\b(na|da|pela)\s+nyxcom",
    r"(mmorpg|10x|economia|falhas? críticas?)[^.]{0,40}\b(na|da|pela)\s+(loja\s+)?mil vidas",
]

# Os 23 casos foram CONSTRUÍDOS, não "obtidos" pela automação.
# Pega verbos ("gerando 23 casos") e parênteses ("Playwright (23 casos").
CASOS_COMO_RESULTADO = (
    r"automat\w+[^.]{0,120}"
    r"((obtendo|gerando|resultando em|com)\s+|\(\s*)23 casos"
)

# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def base():
    return yaml.safe_load((DATA / "base.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cv():
    return yaml.safe_load((DATA / "cv_vaga.yaml").read_text(encoding="utf-8"))


# ---------- Helpers ----------
def _bullets(doc):
    return {b["id"]: b["texto"] for e in doc["experiencias"] for b in e["bullets"]}


def _texto_completo(doc):
    return yaml.safe_dump(doc, allow_unicode=True, width=10_000).lower()


def _todos_textos(doc):
    return list(doc["resumos"].values()) + list(_bullets(doc).values())


def _numeros_de_resultado(texto):
    """Números do texto, ignorando '285' (carga horária) e anos (19xx/20xx)."""
    return [
        n for n in re.findall(r"\d+", texto)
        if n != "285" and not re.fullmatch(r"(19|20)\d{2}", n)
    ]


# ---------- Contrato de schema ----------
def test_mesmas_chaves(base, cv):
    assert set(base) == set(cv)


# ---------- Anti-alucinação ----------
@pytest.mark.parametrize("ferramenta", PROIBIDAS)
def test_sem_ferramentas_inventadas(cv, ferramenta):
    assert ferramenta not in _texto_completo(cv)


@pytest.mark.parametrize("secao", ["experiencias", "projetos", "formacao"])
def test_sem_itens_inventados(base, cv, secao):
    ids_base = {i["id"] for i in base[secao]}
    ids_cv = {i["id"] for i in cv[secao]}
    assert ids_cv <= ids_base, f"IDs novos: {ids_cv - ids_base}"


def test_sem_bullets_inventados(base, cv):
    novos = set(_bullets(cv)) - set(_bullets(base))
    assert not novos, f"Bullets inventados: {novos}"


def test_sem_numeros_inventados(base, cv):
    nums_base = set(re.findall(r"\d+", _texto_completo(base)))
    nums_cv = set(re.findall(r"\d+", _texto_completo(cv)))
    assert nums_cv <= nums_base, f"Números inventados: {nums_cv - nums_base}"


def test_skills_existem_no_base(base, cv):
    nomes_base = {s["nome"] for s in base["skills"]}
    for s in cv["skills"]:
        assert s["nome"] in nomes_base, f"Skill inventada: {s['nome']}"


@pytest.mark.parametrize("termo", TERMOS_INFLADOS, ids=lambda t: re.sub(r"[^\w ]", "", t))
def test_sem_termos_inflados(cv, termo):
    achado = re.search(termo, _texto_completo(cv))
    assert not achado, f"Termo inflado encontrado: '{achado.group()}'"


# ---------- Fidelidade aos fatos ----------
@pytest.mark.parametrize("chave", TIPOS_RESUMO)
def test_fatos_nao_misturam_experiencias(cv, chave):
    texto = cv["resumos"][chave].lower()
    for padrao in ATRIBUICOES_ERRADAS:
        achado = re.search(padrao, texto)
        assert not achado, f"'{chave}': fato atribuído à empresa errada → '{achado.group()}'"


@pytest.mark.parametrize("chave", TIPOS_RESUMO)
def test_casos_de_teste_nao_sao_resultado_da_automacao(cv, chave):
    achado = re.search(CASOS_COMO_RESULTADO, cv["resumos"][chave].lower())
    assert not achado, f"'{chave}': distorce o fato da base → '{achado.group()}'"


# ---------- Preservação ----------
@pytest.mark.parametrize("metrica", METRICAS_OBRIGATORIAS)
def test_metricas_preservadas(cv, metrica):
    assert metrica.lower() in _texto_completo(cv), f"Métrica perdida: '{metrica}'"


def test_resumo_manual_mantem_2_falhas(cv):
    assert "2 falhas críticas" in cv["resumos"]["manual"]


def test_resumo_geral_cita_nyxcom(cv):
    assert "NyxCom" in cv["resumos"]["geral"]


def test_idiomas_intactos(base, cv):
    if "idiomas" not in base:
        pytest.skip("base.yaml não tem a chave 'idiomas'")
    assert cv["idiomas"] == base["idiomas"], "Idiomas foram alterados pela IA"


# ---------- Integridade de dados ----------
def test_datas_e_empresas_intactas(base, cv):
    originais = {e["id"]: (e["empresa"], e["inicio"], e["fim"]) for e in base["experiencias"]}
    for e in cv["experiencias"]:
        assert (e["empresa"], e["inicio"], e["fim"]) == originais[e["id"]]


# ---------- Qualidade do conteúdo ----------
@pytest.mark.parametrize("chave", TIPOS_RESUMO)
def test_resumo_tem_tamanho_minimo(cv, chave):
    tamanho = len(cv["resumos"][chave])
    assert tamanho >= 250, f"Resumo '{chave}' curto demais ({tamanho} caracteres)"


@pytest.mark.parametrize("chave", TIPOS_RESUMO)
def test_resumo_tem_resultado_com_numero(cv, chave):
    nums = _numeros_de_resultado(cv["resumos"][chave])
    assert nums, f"Resumo '{chave}' sem resultado numérico (além de 285h e anos)"


# ---------- Formatação ----------
def test_textos_sem_quebra_no_fim(cv):
    sujos = [t[:40] for t in _todos_textos(cv) if t != t.strip()]
    assert not sujos, f"Textos com espaço/quebra no fim: {sujos}"


def test_sem_espacos_duplos(cv):
    sujos = [t[:40] for t in _todos_textos(cv) if "  " in t]
    assert not sujos, f"Textos com espaço duplo: {sujos}"
