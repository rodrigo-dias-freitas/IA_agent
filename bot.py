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
Você é o SFLIM Tactical Radar, um agente de inteligência de mercado especializado em fornecer micro-viés e mapeamento de zonas de interesse para operações de SCALPING (janelas de 5 a 30 minutos).

DIRETRIZES DE ARQUITETURA E COMPORTAMENTO (Versão 2.3.0 - Tactical Scalp Radar):
1. **Zero Ordens Cravadas / Zero Execução Automática:** NUNCA forneça preços fixos de entrada, stop loss numérico ou ordens mecânicas. A execução e o timing do gatilho gráfico pertencem inteiramente ao operador humano.
2. **Micro-Viés de Curto Prazo (TTL 15-30 min):** Avalie o print e o contexto imediato para ditar a direção do fluxo de curtíssimo prazo nas barras de M1/M5.
3. **Mapeamento de Zona de Interesse (Geografia de Preço):** Em vez de um preço exato, indique a **zona de confluência ou média móvel** (ex: região da EMA 9/20 ou suporte/resistência recente) onde o preço tende a reagir.
4. **Alerta de Volatilidade e Ruído:** Avise sobre momentos de exaustão de movimento, falta de clareza ou risco de notícias imediatas.
5. **Formato de Saída (Radar Tático e Executivo):**
   - ⚡ **Micro-Viés (Próximos 15-30 min):** [COMPRA RÁPIDA / VENDA RÁPIDA / NEUTRO - AGUARDAR]
   - ⏱️ **Validade do Viés:** [Janela de 15 a 30 minutos]
   - 🗺️ **Zona de Interesse (Atenção):** [Descreva a região de preço/média onde o trader deve monitorar o preço]
   - 🎯 **Gatilho Visual (Para o Trader Executar):** [Instrução comportamental do que observar no candle, ex: "Aguardar teste na EMA e rejeição com pavio para operar a favor do fluxo"]
   - 💡 **Síntese Operacional:** [Instrução direta de 1 frase]
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

    await update.message.reply_text("🔎 *Analisando o gráfico com o SFLIM Agent...*", parse_mode="Markdown")

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