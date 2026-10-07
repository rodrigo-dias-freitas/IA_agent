import os
from google import genai
from pydantic import BaseModel, Field

# 1. Inicializar o cliente Gemini
# Certifique-se de que a variável $env:GEMINI_API_KEY está definida
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

class ContextoMercado(BaseModel):
    ativo: str
    noticias_drivers: str
    dados_tecnicos_5min: str

def analisar_cenario(dados: ContextoMercado) -> str:
    prompt = f"""
    Você é um Analista Macro e de Microestrutura de Mercado.
    Avalie o cenário para o ativo {dados.ativo}:

    • DRIVERS MACRO / NOTÍCIAS: {dados.noticias_drivers}
    • TÉCNICO (5 MINUTOS): {dados.dados_tecnicos_5min}

    Determine de forma extremamente objetiva:
    1. A Tendência Macro (ALTA, BAIXA ou CONSOLIDAÇÃO) e o motivo principal.
    2. A Tendência do Gráfico de 5 Minutos (ALTA, BAIXA ou CONSOLIDAÇÃO) e a estrutura de preço.
    3. Se há alinhamento entre Macro e 5min.

    FORMATO DA RESPOSTA:
    📊 **ANÁLISE DE TENDÊNCIA - {dados.ativo}**
    • **Tendência Macro:** [DIREÇÃO] - (Motivo)
    • **Tendência 5 Minutos:** [DIREÇÃO] - (Estrutura)
    • **Alinhamento:** [ALINHADOS / DIVERGENTES]
    • **Vés Operacional:** (Comprado, Vendido ou Neutro)
    """

    response = client.models.generate_content(
        model='gemini-3.8-flash', 
        contents=prompt,
    )
    return response.text

if __name__ == "__main__":
    exemplo = ContextoMercado(
        ativo="US100 (Nasdaq)",
        noticias_drivers="DXY em alta forte (+0.40%), Yields do US10Y subindo. Payroll veio bem acima da expectativa.",
        dados_tecnicos_5min="Preço perdeu a VWAP e fechou pivô de baixa rompendo o fundo da consolidação do pré-market."
    )

    print("\n⏳ Enviando dados para o Gemini...\n")
    print(analisar_cenario(exemplo))