import os
import joblib
import pandas as pd
from db_connection import get_connection
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

# 1. Coletar os dados
def coletar_dados():
    conn = get_connection()
    query = "SELECT * FROM indicadores_fundamentalistas"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# 2. Limpeza e preparação dos dados
def limpar_dados(df):
    # Remover colunas desnecessárias
    df = df.drop(columns=["acao", "data_coleta"])

    # Remover linhas com dados faltantes
    df = df.dropna()

    # Garantir que as colunas sejam do tipo string antes de fazer o replace
    df['pl'] = df['pl'].astype(str).str.replace(',', '.').astype(float)
    df['dividend_yield'] = df['dividend_yield'].astype(str).str.replace(',', '.').astype(float)

    return df

# 3. Definir rótulos de recomendação
def adicionar_rotulos(df):
    df["recomendado"] = ((df["pl"] < 10) & (df["dividend_yield"] > 5) & (df["roe"] > 15)).astype(int)
    return df

# 4. Treinar o modelo
def treinar_modelo(df):
    X = df.drop(columns=["recomendado"])
    y = df["recomendado"]

    # Dividir os dados em treino e teste
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Inicializar o modelo de classificação
    modelo = RandomForestClassifier(n_estimators=100, random_state=42)

    # Treinar o modelo
    modelo.fit(X_train, y_train)

    # Avaliar o modelo
    y_pred = modelo.predict(X_test)
    print("Acurácia:", accuracy_score(y_test, y_pred))
    print("\nRelatório de Classificação:\n", classification_report(y_test, y_pred))

    return modelo

# 5. Salvar o modelo treinado
def salvar_modelo(modelo):
    # Definir o caminho dinâmico baseado no diretório atual
    base_path = os.path.dirname(os.path.abspath(__file__))  # Obtém o diretório onde o script está sendo executado
    modelo_path = os.path.join(base_path, "modelo", "modelo_classificador.pkl")  # Caminho final para salvar o modelo

    # Salvar o modelo no diretório desejado
    joblib.dump(modelo, modelo_path)
    print(f"Modelo salvo com sucesso em {modelo_path}")

# 6. Executar todo o pipeline
def executar():
    df = coletar_dados()
    df = limpar_dados(df)
    df = adicionar_rotulos(df)
    modelo = treinar_modelo(df)
    salvar_modelo(modelo)

if __name__ == "__main__":
    executar()
