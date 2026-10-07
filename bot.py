import os
import io
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
import time

# Configurações do ambiente
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

USUARIOS_AUTORIZADOS = [
    8704058004
]

# Inicializa o cliente Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

async def processar_midia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🛑 VERIFICAÇÃO DE SEGURANÇA: Bloqueia utilizadores não autorizados
    user_id = update.effective_user.id
    if user_id not in USUARIOS_AUTORIZADOS:
        print(f"⚠️ Acesso negado para o ID não autorizado: {user_id}")
        await update.message.reply_text("⛔ Acesso restrito. Este bot é privado.")
        return
    await update.message.reply_text("🔎 *Analisando gráfico com o SFLIM Agent...*", parse_mode="Markdown")



    prompt_instrucao = """
    Você é um Analista Macro e de Microestrutura de Mercado.
    Examine a imagem do gráfico enviada e/ou o texto de contexto.

    Determine de forma extremamente objetiva:
    1. A Tendência Macro (ALTA, BAIXA ou CONSOLIDAÇÃO) e o motivo principal (se citado no texto ou contexto).
    2. A Tendência do Gráfico de 5 Minutos (ALTA, BAIXA ou CONSOLIDAÇÃO) identificando a estrutura visual do gráfico (posição da VWAP, topos e fundos, pivôs, suportes/resistências).
    3. Se há alinhamento entre Macro e 5min.

    FORMATO DA RESPOSTA:
    📊 **ANÁLISE DE TENDÊNCIA**
    • **Tendência Macro:** [DIREÇÃO] - (Motivo)
    • **Tendência 5 Minutos:** [DIREÇÃO] - (Estrutura visual observada no gráfico)
    • **Alinhamento:** [ALINHADOS / DIVERGENTES]
    • **Viés Operacional:** (Comprado, Vendido ou Neutro)
    """

    conteudo_gemini = [prompt_instrucao]

    # Se o usuário enviou uma legenda junto com a foto ou apenas texto
    legenda_ou_texto = update.message.caption or update.message.text
    if legenda_ou_texto:
        conteudo_gemini.append(f"\nContexto informado pelo usuário: {legenda_ou_texto}")

    # Se o usuário enviou uma Foto
    if update.message.photo:
        foto_file = await update.message.photo[-1].get_file()
        foto_bytes = await foto_file.download_as_bytearray()
        imagem_pil = Image.open(io.BytesIO(foto_bytes))
        conteudo_gemini.append(imagem_pil)

    try:
        # Lista de modelos por ordem de preferência para fallback
        modelos_fallback = ['gemini-3.8-flash']
        resposta_texto = None

        for modelo in modelos_fallback:
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=conteudo_gemini,
                )
                resposta_texto = response.text
                break  # Se funcionar, sai do loop
            except Exception as err_model:
                if "503" in str(err_model) or "UNAVAILABLE" in str(err_model):
                    print(f"⚠️ Servidor ocupado no modelo {modelo}. Aguardando 2s e tentando alternativa...")
                    time.sleep(2)
                    continue
                else:
                    raise err_model

        if resposta_texto:
            await update.message.reply_text(resposta_texto)
        else:
            await update.message.reply_text("⚠️ Servidores do Gemini instáveis no momento. Tente novamente em alguns segundos.")

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao analisar: {str(e)}")
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Processa mensagens com Texto OU Fotos
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_midia))

    print("🚀 Bot Multimodal (Texto + Imagem) rodando...")
    app.run_polling()