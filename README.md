# 📄 CV Generator — Currículos adaptados por vaga com IA

Gera currículos em PDF **personalizados para cada vaga**, usando IA (Google Gemini) para adaptar o resumo profissional, com **validação automática**, **revisão humana** e **testes como quality gate** antes da geração final.

> Projeto criado para resolver um problema real: adaptar o currículo manualmente para cada vaga é lento e repetitivo.

## ✨ Funcionalidades

- 🎯 Detecção automática do foco da vaga (`automacao`, `api`, `manual` ou `geral`)
- 🤖 Adaptação do resumo via **Gemini**, usando os termos da vaga (ATS)
- 🛡️ **Validação da saída da IA**: tamanho, métricas reais, termos proibidos e frases obrigatórias, com até 3 tentativas de autocorreção
- 🔒 Bullets e projetos **restaurados do original**: a IA só reordena, nunca inventa
- 👤 **Revisão humana**: aprovar, editar ou regerar o resumo
- 🗂️ **Banco de resumos aprovados**, usado como referência nas próximas vagas
- 🧪 **pytest como quality gate**: se algum teste falhar, o PDF não é gerado
- 🧾 PDF gerado com **Playwright** a partir de template **Jinja2**
- 📚 Histórico do CV usado em cada vaga

## 🛠️ Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.x |
| IA | Google Gemini API (`google-genai`) |
| Template | Jinja2 + HTML/CSS |
| PDF | Playwright (Chromium) |
| Dados | YAML |
| Testes | pytest |

## 📁 Estrutura

```
├── data/            # Dados base do CV (YAML), vagas e banco de resumos
├── src/             # ia.py (pipeline), pdf.py, avaliar.py
├── templates/       # Template HTML do currículo
├── tests/           # Testes de qualidade do CV
├── scripts/         # Utilitários de setup/diagnóstico
└── generate.py      # Gera o CV base (sem IA)
```

## 🚀 Instalação

```bash
git clone https://github.com/brunnoc-04/cv-generator1.git
cd cv-generator1
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

Configure seus dados:

```bash
cp .env.example .env                           # adicione sua GEMINI_API_KEY
cp data/pessoal.example.yaml data/pessoal.yaml # seus dados pessoais
```

## ▶️ Uso

**CV adaptado para uma vaga** (com IA): salve o texto da vaga em `data/vagas/` (ex.: `2026-11-11_empresa_qa.txt`) e execute:

```bash
python src/ia.py                                    # usa a vaga .txt mais recente
python src/ia.py data/vagas/2026-11-11_empresa_qa.txt  # vaga específica
python src/ia.py --so-pdf                           # regera o PDF sem chamar a IA
```

O PDF final vai para `output/vagas/cv_<nome_da_vaga>.pdf`.

**CV base** (sem IA):

```bash
python generate.py
```

## 🧪 Testes

```bash
pytest -v
```

Os testes também rodam automaticamente dentro do pipeline, antes da geração do PDF.

## 🔄 Fluxo

```
Vaga (.txt) → Detecção do foco → Gemini adapta resumo → Validação (até 3 tentativas)
→ Revisão humana → Banco de aprovados → pytest (quality gate) → PDF (Playwright) → Histórico
```

## 🗺️ Próximos passos

- [ ] CI com GitHub Actions rodando os testes
- [ ] Relatório de testes em HTML
- [ ] Suporte a múltiplos templates

## 👨‍💻 Autor

**Brunno Cesar Noronha** — QA Engineer em formação
[LinkedIn](https://www.linkedin.com/in/brunnocesar04/) · [GitHub](https://github.com/brunnoc-04)
