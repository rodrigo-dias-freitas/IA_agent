import os

# 1. FORÇAR O PROXY DO PYTHONANYWHERE NAS VARIÁVEIS DE AMBIENTE (Antes de tudo)
os.environ["HTTP_PROXY"] = "http://proxy.server:3128"
os.environ["HTTPS_PROXY"] = "http://proxy.server:3128"
os.environ["http_proxy"] = "http://proxy.server:3128"
os.environ["https_proxy"] = "http://proxy.server:3128"

import io
import asyncio
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from dotenv import load_dotenv
from telegram.request import HTTPXRequest

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

        # Captura o texto da legenda ou assume 0.06 por padrão
        user_caption = (update.message.caption or "").strip()
        lote_informado = user_caption if user_caption else "0.06"
        
        prompt = f"""
        Atua como um analista técnico e macroeconómico especializado em trading intraday.

        INFORMAÇÃO DE LOTE DO USUÁRIO: "{lote_informado}"
        REGRA RÍGIDA DE LOTE: 
        - Se a legenda enviada não for um número válido ou for menor que 0.06 (ou estiver vazia), CONSIDERE O LOTE DE 0.06.
        - O lote mínimo operacional é 0.06.

        Sua tarefa:
        1. Identifique o ativo e o tempo gráfico presente na imagem.
        2. Determine o ponto de Entrada (preço atual/gatilho), o nível técnico ideal de STOP LOSS (SL) e o TAKE PROFIT (Alvo/TP).
        3. Com base no lote definido (mínimo 0.06), CALCULE o valor do risco em dinheiro ($ USD) e em pontos/pips.
        4. Realize a pesquisa no Google para buscar as NOTÍCIAS MAIS RECENTES do dia e os EVENTOS DO CALENDÁRIO ECONÔMICO para este ativo.

        Estrutura obrigatoria da resposta:
        • **Ativo & Contexto:** [Nome do ativo e Tempo Gráfico]
        • **Configuração da Ordem:** Entrada [Preço] | SL [Preço] | TP [Preço]
        • **Gestão de Risco & Tamanho da Posição (Lote: {lote_informado}):**
           - **Prejuízo Máximo (se bater no SL):** -$[Valor] USD ([X] pontos / pips)
           - **Lucro Projetado (se atingir o Alvo):** +$[Valor] USD ([X] pontos / pips)
           - **Relação Risco x Retorno:** [Ex: 1 : 2.5]
        • **Leitura Técnica & Notícias:** [Análise de Price Action + Notícias e Calendário do dia]
        • **Viés Operacional & Alerta:** [Comprador / Vendedor / Neutro + Orientação de Risco]
        """

        # 4. Sessão de Chat com Google Search Grounding ativo
        chat = client.chats.create(
            model="gemini-3.8-flash",
            config={
                "tools": [{"google_search": {}}]  # Ativa a pesquisa de notícias no Google
            }
        )

        # Timeout de 45 segundos para a requisição não travar
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: chat.send_message(message=[image, prompt])),
            timeout=45.0
        )

        # 5. Enviar a resposta para o Telegram
        try:
            await update.message.reply_text(response.text, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(response.text)

    except asyncio.TimeoutError:
        await update.message.reply_text("⏱️ A consulta demorou muito para responder (timeout). Por favor, envie a foto novamente.")
    except Exception as e:
        print(f"Erro no processamento: {e}")
        await update.message.reply_text(f"⚠️ Ocorreu um erro ao processar a análise: {str(e)}")

if __name__ == "__main__":
    # Configura o proxy gratuito obrigatório do PythonAnywhere
    request_config = HTTPXRequest(
        proxy="http://proxy.server:3128",
        connect_timeout=30.0,
        read_timeout=30.0
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .request(request_config)
        .build()
    )
    
    app.add_handler(MessageHandler(filters.PHOTO, processar_midia))
    print("🚀 Agente do Telegram SFLIM ativo via Proxy...")
    app.run_polling()