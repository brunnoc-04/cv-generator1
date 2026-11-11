# 📄 CV Generator — Currículos adaptados por vaga com IA

Gera currículos em PDF **personalizados para cada vaga**, usando IA (Google Gemini) para adaptar o resumo profissional, com **revisão humana** antes da geração final.

> Projeto criado para resolver um problema real: adaptar o currículo manualmente para cada vaga é lento e repetitivo.

## ✨ Funcionalidades

- 🤖 Adaptação do resumo ao texto da vaga via **Gemini**
- 👤 **Revisão humana** do resumo antes de gerar o PDF
- 🗂️ **Banco de resumos aprovados**, reaproveitados em vagas parecidas
- 🧾 Geração de PDF com **Playwright** a partir de um template HTML
- 📊 Avaliação de aderência do CV à vaga (`src/avaliar.py`)
- 🔒 Dados pessoais e chaves fora do repositório (`.env` / `pessoal.yaml`)
- ✅ Testes automatizados com **pytest**

## 🛠️ Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.x |
| IA | Google Gemini API |
| PDF | Playwright (Chromium) |
| Dados | YAML |
| Testes | pytest |

## 📁 Estrutura

```
├── data/            # Dados base do CV (YAML) e exemplos
├── src/             # Lógica: IA, PDF, avaliação
├── templates/       # Template HTML do currículo
├── tests/           # Testes automatizados
├── scripts/         # Utilitários de setup/diagnóstico
└── generate.py      # Ponto de entrada
```

## 🚀 Como rodar

```bash
git clone https://github.com/brunnoc-04/cv-generator1.git
cd cv-generator1
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

Configure:

```bash
cp .env.example .env                          # adicione sua GEMINI_API_KEY
cp data/pessoal.example.yaml data/pessoal.yaml # seus dados pessoais
```

Coloque o texto da vaga em `data/vagas/` e execute:

```bash
python generate.py   <!-- ajuste: argumentos reais -->
```

O PDF é gerado em `output/`.

## 🧪 Testes

```bash
pytest -v
```

## 🔄 Fluxo

```
Vaga (.txt) → Gemini adapta resumo → Revisão humana → Banco de aprovados → Template HTML → PDF (Playwright)
```

## 🗺️ Próximos passos

- [ ] CI com GitHub Actions rodando os testes
- [ ] Relatório de testes em HTML
- [ ] Suporte a múltiplos templates

## 👨‍💻 Autor

**Brunno Cesar Noronha** — QA Engineer em formação
[LinkedIn](<!-- seu link -->) · [GitHub](https://github.com/brunnoc-04)
