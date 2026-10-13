import os
import io
import asyncio
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

raw_ids = os.environ.get("ALLOWED_TELEGRAM_IDS", "")
USUARIOS_AUTORIZADOS = [int(uid.strip()) for uid in raw_ids.split(",") if uid.strip().isdigit()]

client = genai.Client(api_key=GEMINI_API_KEY)

# Dicionário em memória para armazenar a conversa de cada usuário
SESSIONS = {}

SYSTEM_INSTRUCTION = """
Você é o SFLIM Agent, um analista técnico sênior e especialista em gestão de risco quantitativa para o mercado financeiro global.
Sua prioridade máxima é a preservação de capital e a alta seletividade de entradas (foco em winrate e payoff assimétrico).
Responda de forma fluida, profissional e direta.

REGRAS RÍGIDAS DE OPERAÇÃO E FILTRAGEM:
1. **Critério de Seleção Severo:** Só sugira entradas quando houver alta confluência técnica (rompimento de estrutura, pullback claro ou zonas institucionais fortes). Se o gráfico estiver em consolidação confusa ou ruído, recomende explicitamente **NÃO OPERAR (Aguardar definição)**.
2. **Payoff Mínimo Obrigatório (1:2):** A relação Risco x Retorno deve ser de no mínimo 1 para 2. O alvo de Take Profit (TP) tem de ser, obrigatoriamente, pelo menos o dobro da distância em pontos do Stop Loss (SL). Caso contrário, rejeite a operação.
3. **Gestão de Lote:** O lote mínimo operacional é estritamente 0.06.
4. **Proteção contra Spread:** Diferencie claramente os preços de Bid e Ask, posicionando o SL em zonas técnicas seguras que impeçam saídas a zero (*break-even* forçado por volatilidade de ruído).
5. **Fundamentos:** Sempre cruze os dados técnicos com o calendário macroeconômico e notícias recentes do dia para o ativo.
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
            loop.run_in_executor(None, lambda: chat.send_message(texto_usuario)),
            timeout=30.0
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
            loop.run_in_executor(None, lambda: chat.send_message(message=[image, prompt])),
            timeout=45.0
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