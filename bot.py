import os
import io
import asyncio
import time
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from dotenv import load_dotenv
from google.genai.errors import APIError

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

raw_ids = os.environ.get("ALLOWED_TELEGRAM_IDS", "")
USUARIOS_AUTORIZADOS = [int(uid.strip()) for uid in raw_ids.split(",") if uid.strip().isdigit()]

client = genai.Client(api_key=GEMINI_API_KEY)

# Dicionário em memória para armazenar a conversa de cada usuário
SESSIONS = {}

SYSTEM_INSTRUCTION = """
Você é o SFLIM Agent, um analista técnico sênior e especialista em gestão de risco quantitativa para o mercado financeiro global e nacional (Forex, Índices Globais e B3).
Sua prioridade máxima é a preservação de capital, o controle rígido de risco e a alta seletividade de entradas. NUNCA estabeleça ou cobre metas de lucro diário, pois o foco absoluto é o processo e a gestão de risco.

REGRAS RÍGIDAS DE OPERAÇÃO E FILTRAGEM (Versão 1.1.1):
1. **Alinhamento Direcional Obrigatório (Macro x Micro):** Você deve identificar primeiramente o viés macro do ativo. É TERMINANTEMENTE PROIBIDO dar duplo sentido ou sugerir operações contra a tendência principal. Se o viés macro é de COMPRA, você só deve apontar e recomendar gatilhos de COMPRA. Se o viés é de VENDA, você só deve apontar gatilhos de VENDA. Se o gráfico atual estiver divergente ou confuso, decrete imediatamente [🔴 NÃO OPERAR / AGUARDAR].
2. **Veredito Imediato e Único:** Na primeira linha da sua análise, você DEVE declarar o veredito de forma frontal e sem ambiguidade ([🟢 ENTRADA AUTORIZADA] ou [⛔ NÃO OPERAR / AGUARDAR]). Nunca apresente estratégias simultâneas de "se subir faz X, se cair faz Y". Seja decisivo.
3. **Trava de Volatilidade por Janela de Notícias e Abertura de Mercado:** 
   - Se a análise for feita a **menos de 30 minutos da abertura do pregão** correspondente (ex: abertura de Wall Street às 10:30 BRT para Índices EUA, ou abertura da B3 às 10:00 BRT para Mini-Índice/Mini-Dólar), DECRETE IMEDIATAMENTE [⛔ NÃO OPERAR / BLOQUEIO DE ABERTURA].
   - Se houver **notícias de alto impacto no calendário econômico** (ex: CPI, Payroll, FOMC, Decisão de Juros, PIB, IPCA) nos **30 minutos anteriores ou posteriores** ao horário atual, DECRETE IMEDIATAMENTE [⛔ NÃO OPERAR / BLOQUEIO DE CALENDÁRIO], alertando explicitamente sobre a projeção do indicador e o risco de alargamento de spread e estopada por volatilidade atípica.
4. **Payoff Mínimo Obrigatório (1:2) com Realismo:** A relação Risco x Retorno deve ser de no mínimo 1 para 2. Se o Stop Loss técnico (baseado em médias móveis distantes como EMA 200) for excessivamente grande a ponto de inviabilizar o alvo no fluxo atual, declare a operação inviável por amplitude.
5. **Gestão de Lote, Detecção de Moeda e Cálculos Explícitos:** 
   - Identifique visualmente na imagem a moeda da conta e do ativo (ex: R$ para B3, USD para mercados globais/Forex). 
   - Considere sempre o lote operacional efetivo alinhado à plataforma.
   - Inclua obrigatoriamente no relatório o cálculo financeiro estimado de perda (Stop Loss) e ganho (Take Profit) **na moeda correta da conta exibida no print** para facilitar a tomada de decisão rápida.
6. **Proteção contra Spread:** Diferencie claramente os preços de Bid e Ask, posicionando o SL em zonas técnicas seguras contra ruídos de volatilidade.
- Você tem acesso à busca na web para consultar cotações e notícias em tempo real quando o usuário perguntar sobre o mercado.
"""

def get_chat_session(user_id: int):
    """Obtém ou cria uma sessão de chat persistente para o usuário."""
    if user_id not in SESSIONS:
        SESSIONS[user_id] = client.chats.create(
            model="gemini-3.8-flash",
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "tools": [{"google_search": {}}]
            }
        )
    return SESSIONS[user_id]

def chamada_gemini_com_retry(chat_or_client, contents, model_name="gemini-3.8-flash", max_retries=3, delay=5):
    """Executa o envio de mensagens para o chat ou modelo com tentativas automáticas em caso de erro 503."""
    for tentativa in range(1, max_retries + 1):
        try:
            # Se for um chat do Gemini (chat.send_message)
            if hasattr(chat_or_client, "send_message"):
                return chat_or_client.send_message(message=contents)
            # Se for chamada direta ao client.models
            else:
                return chat_or_client.models.generate_content(model=model_name, contents=contents)
        except APIError as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if tentativa < max_retries:
                    print(f"⚠️ Servidor do Gemini sobrecarregado (Tentativa {tentativa}/{max_retries}). A tentar novamente em {delay}s...")
                    time.sleep(delay)
                    delay *= 2  # Aumento exponencial
                    continue
            raise e
        except Exception as e:
            # Trata também erros genéricos que possam conter 503 na mensagem
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if tentativa < max_retries:
                    print(f"⚠️ Servidor sobrecarregado (Tentativa {tentativa}/{max_retries}). A tentar novamente em {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue
            raise e
    raise Exception("❌ O Gemini continua indisponível após várias tentativas devido a alta demanda.")

async def enviar_mensagem_dividida(update: Update, texto: str):
    """Envia mensagens divididas em partes menores se excederem o limite do Telegram."""
    max_length = 4000  # Limite de caracteres do Telegram
    if len(texto) <= max_length:
        try:
            await update.message.reply_text(texto, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(texto)
    else:
        for i in range(0, len(texto), max_length):
            parte = texto[i:i + max_length]
            try:
                await update.message.reply_text(parte, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(parte)

async def processar_mensagem_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USUARIOS_AUTORIZADOS and user_id not in USUARIOS_AUTORIZADOS:
        return

    texto_usuario = update.message.text
    chat = get_chat_session(user_id)

    await update.message.reply_chat_action("typing")

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: chamada_gemini_com_retry(chat, texto_usuario)),
            timeout=40.0
        )
        
        # Tenta enviar com Markdown, se falhar por erro de entidade, envia como texto normal
        try:
            await enviar_mensagem_dividida(update, response.text)
        except Exception:
            await enviar_mensagem_dividida(update, response.text)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao processar mensagem: {str(e)}")

async def processar_midia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USUARIOS_AUTORIZADOS and user_id not in USUARIOS_AUTORIZADOS:
        return

    await update.message.reply_text("🔎 *Analisando o gráfico com o SFLIM Agent (Lote min: 0.06 | Foco R:R 1:2+)...*", parse_mode="Markdown")

    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        image = Image.open(io.BytesIO(image_bytes))

        user_caption = (update.message.caption or "").strip()
        lote_informado = user_caption if user_caption else "0.06"

        prompt = f"""
        Analise a imagem deste gráfico de trading rigorosamente sob as regras de gestão de risco e payoff mínimo de 1:2.
        Informação do lote enviado pelo usuário: "{lote_informado}" (Lote mínimo: 0.06).
        
        Realize a leitura técnica completa, verifique se há confluência real para entrada, defina SL, TP (verificando se atinge a proporção mínima de 1:2), calcule o risco em USD e verifique as notícias de hoje para este ativo. Caso não haja oportunidade clara, recomende aguardar.
        """

        chat = get_chat_session(user_id)

        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: chamada_gemini_com_retry(chat, [image, prompt])),
            timeout=50.0
        )
        
        # Bloco protegido contra falhas de Markdown
        try:
            await enviar_mensagem_dividida(update, response.text)
        except Exception:
            await enviar_mensagem_dividida(update, response.text)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Erro ao analisar a imagem: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Manipulador para fotos
    app.add_handler(MessageHandler(filters.PHOTO, processar_midia))
    # Manipulador para mensagens de texto (perguntas diretas)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem_texto))
    
    print("🚀 Agente do Telegram SFLIM ativo (Texto + Visão + Gestão Otimizada)...")
    app.run_polling()