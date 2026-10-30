# ⚡ SFLIM Agent — Tactical Scalp Radar & Micro-Bias Synthesizer (v2.3.0)

O **SFLIM Agent** é um co-piloto e assistente de inteligência de mercado focado no apoio à tomada de decisão para **SCALPING (janelas de 5 a 30 minutos)**.

Projetado sob a arquitetura de *Decision Support System* (DSS), o agente varre catalisadores macroeconômicos, fluxo de notícias, calendário e sentimento do mercado para entregar **Micro-Viés dinâmico** e **Mapeamento de Zonas de Interesse**, mantendo o gatilho final de execução e o gerenciamento de risco sob controle humano total.

---

## 🎯 Arquitetura & Filosofia (v2.3.0)

A partir da versão **v2.3.0**, o SFLIM abandonou a recomendação mecânica de preços engessados (que geravam latência operacional) e assumiu o papel de **Radar Tático**:

1. **Zero Ordens Automáticas / Responsabilidade Humana:** O agente atua de forma estritamente *advisory*. A ordem final e o clique pertencem ao trader.
2. **Micro-Viés Dinâmico (TTL 15-30 min):** Mapeamento do fluxo de curto prazo nas barras de M1/M5 com base nos catalisadores imediatos.
3. **Geografia de Preço (Zonas de Interesse):** Sinalização de regiões de confluência (médias móveis como EMA 9/20 e suportes/resistências chave) onde o preço tende a reagir.
4. **Gatilho Visual para Execution:** Indicação técnica de padrões gráficos no M1/M5 (pavios de rejeição, quebra de micro-estruturas) que autorizam a entrada.

---

## 🖥️ Setup Operacional Recomendado

Para potencializar o uso do SFLIM Agent, recomenda-se a navegação em **Análise Múltipla de Timeframes (MTFA)** com tela dividida em 3 janelas:

- **Gráfico Maior (M15 / M30):** Filtro de tendência macro e médias de peso.
- **Gráfico Intermediário (M5):** Mapeamento da Zona de Interesse e estrutura imediata.
- **Gráfico Menor (M1):** Timing do clique, observação do pavio de rejeição e Stop Loss reduzido.

---

## 📱 Formato de Saída (Telegram)

```text
⚡ [SFLIM TACTICAL RADAR — SCALP 5-30M]

* ⚡ Micro-Viés: VENDA RÁPIDA (BEARISH FLUXO)
* ⏱️ Validade: Próximos 20 minutos
* 🗺️ Zona de Interesse: Região entre a EMA 9 e a EMA 20 no M5
* 🎯 Gatilho Visual: Aguardar teste nas médias com rejeição (pavio superior). Entrada na perda da mínima do candle M1.
* 💡 Síntese: Trabalhe a favor do fluxo vendedor pós-notícia; evite adivinhar fundo.
```

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.11+
- **Orquestração de IA:** LangGraph / Gemini API
- **Validação de Dados:** Pydantic
- **Interface & Alertas:** Telegram Bot API
- **Hospedagem & Automação:** PythonAnywhere


## 🚀 Como Rodar o Projeto
**Clonar o Repositório:**

```text
git clone [https://github.com/rodrigofreitas-dev/sflim_agent.git](https://github.com/rodrigofreitas-dev/sflim_agent.git)
cd sflim_agent

```
**Configurar o Ambiente Virtual & Dependências:**

```text
python -m venv venv
source venv/bin/activate  # Linux/Mac ou venv\Scripts\activate no Windows
pip install -r requirements.txt
```

**Variáveis de Ambiente (.env):**

```text
GEMINI_API_KEY=sua_chave_gemini
TELEGRAM_BOT_TOKEN=seu_token_telegram
TELEGRAM_CHAT_ID=seu_chat_id
```

**Executar o Bot:**

```text
python main.py
```

Desenvolvido por Rodrigo Freitas — UI/UX Designer, Frontend Developer & Financial Consultant.
