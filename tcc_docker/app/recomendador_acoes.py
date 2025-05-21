import os
import pandas as pd
import joblib
from scraper_indicadores import coletar_indicadores  # importe do seu arquivo scraper

def carregar_modelo():
    base_path = os.path.dirname(os.path.abspath(__file__))
    modelo_path = os.path.join(base_path, "modelo", "modelo_classificador.pkl")
    if not os.path.exists(modelo_path):
        raise FileNotFoundError(f"Modelo não encontrado em {modelo_path}")
    return joblib.load(modelo_path)

def recomendar_acao(ticker):
    # Pega indicadores pelo scraper
    resultado = coletar_indicadores(ticker)
    if isinstance(resultado, str):
        # erro retornado do scraper
        print(resultado)
        return

    dados, _ = resultado  # dados é um dict com indicadores

    # Converter dict para DataFrame (modelo espera DataFrame)
    df = pd.DataFrame([dados])

    # Carregar modelo
    modelo = carregar_modelo()

    # Prever se recomenda ou não (1/0)
    pred = modelo.predict(df.drop(columns=["acao", "data_coleta"], errors='ignore'))[0]

    if pred == 1:
        print(f"Ação {ticker.upper()}: RECOMENDADA para compra!")
    else:
        print(f"Ação {ticker.upper()}: NÃO recomendada para compra.")

if __name__ == "__main__":
    ticker = input("Digite o ticker da ação (ex: PETR4): ").strip()
    recomendar_acao(ticker)
