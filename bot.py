import os
import io
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (se existir)
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Lê os IDs permitidos da variável de ambiente
raw_ids = os.environ.get("ALLOWED_TELEGRAM_IDS", "")
# Converte a string "123456789,987654321" numa lista de inteiros [123456789, 987654321]
USUARIOS_AUTORIZADOS = [int(uid.strip()) for uid in raw_ids.split(",") if uid.strip().isdigit()]

# Inicializa o cliente Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

async def processar_midia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🛑 VERIFICAÇÃO DE SEGURANÇA: Bloqueia utilizadores não autorizados
    user_id = update.effective_user.id
    if USUARIOS_AUTORIZADOS and user_id not in USUARIOS_AUTORIZADOS:
        print(f"⚠️ Acesso negado para o ID não autorizado: {user_id}")
        await update.message.reply_text("⛔ Acesso restrito. Este bot é privado.")
        return
    await update.message.reply_text("🔎 *Analisando gráfico com o SFLIM Agent...*", parse_mode="Markdown")

    try:
        # 2. Descarregar a foto enviada
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        image = Image.open(io.BytesIO(image_bytes))

        # Legenda opcional (ex: "WIN1!", "PETR4", "EURUSD")
        user_caption = update.message.caption or "o ativo identificado no gráfico"
        
        prompt = f"""
        Atua como um analista técnico e macroeconómico especializado em trading intraday.

        1. Identifica o ativo e o tempo gráfico presentes na imagem (ou considera a dica: {user_caption}).
        2. Utiliza a ferramenta de pesquisa para encontrar as NOTÍCIAS MAIS RECENTES do dia e os EVENTOS DO CALENDÁRIO ECONÓMICO previstos para hoje para este ativo/mercado.
        3. Realiza a análise técnica da imagem: tendência, níveis chave de suporte e resistência, e padrões de price action.
        4. Cruza a análise técnica do gráfico com o contexto das notícias e eventos do calendário.

        Estrutura a resposta da seguinte forma:
        • **Ativo & Contexto:** [Nome do ativo, tempo gráfico e preço atual]
        • **Leitura Técnica:** [Tendência principal, níveis críticos e padrões visuais]
        • **Notícias & Calendário Económico:** [Principais catalisadores e eventos do dia na web]
        • **Viés Operacional & Risco:** [Confluência final: Comprador, Vendedor ou Neutro/Alerta de Risco]
        """

        # 4. Sessão de Chat com Google Search Grounding ativo
        chat = client.chats.create(
            model="gemini-3.8-flash",
            config={
                "tools": [{"google_search": {}}]  # Ativa a pesquisa de notícias no Google
            }
        )

        response = chat.send_message(
            message=[image, prompt]
        )

        # 5. Enviar a resposta para o Telegram
        await update.message.reply_text(response.text, parse_mode="Markdown")

    except Exception as e:
        print(f"Erro no processamento: {e}")
        await update.message.reply_text(f"⚠️ Ocorreu um erro ao processar a análise: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, processar_midia))
    print("🚀 Agente do Telegram com pesquisa de notícias e gráficos ativo...")
    app.run_polling()