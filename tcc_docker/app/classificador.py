import os, joblib, pandas as pd, numpy as np, psycopg2
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, roc_auc_score
from labeling import calcular_rotulos_desempenho_futuro

# Tenta importar do local padrão do seu projeto TCC
try:
    from app.db_connection import get_connection
except ImportError:
    try:
        from db_connection import get_connection #
        print("Importou 'get_connection' do diretório atual.") #
    except ImportError as e:
        print(f"Erro ao importar 'get_connection': {e}")
        print("Certifique-se de que db_connection.py está acessível e as variáveis de ambiente do DB estão configuradas.")
        exit()


def carregar_dados_completos_do_banco():
    """Carrega TODOS os dados da tabela indicadores_fundamentalistas do banco de dados."""
    conn = None
    try:
        conn = get_connection() #
        # Query para pegar TODAS as colunas de indicadores, ordenadas
        query = "SELECT * FROM indicadores_fundamentalistas ORDER BY acao, data_coleta;"
        df = pd.read_sql_query(query, conn) #
        if 'data_coleta' in df.columns:
            df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        print(f"Todos os indicadores carregados do banco! Shape: {df.shape}")
        return df
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao carregar dados do banco: {error}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close() #


def calcular_features_graham_estrito(df_input):
    """
    Calcula o VI de Graham e a feature Preco_Sobre_Graham de forma estrita.
    VI_Graham só é calculado se LPA > 0 E VPA > 0.
    """
    df = df_input.copy()
    cols_to_numeric = ['lpa', 'vpa', 'cotacao']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            df[col] = np.nan
            
    df['vi_graham'] = np.nan
    df['preco_sobre_graham'] = np.nan
    condicao_valida_graham = (df['lpa'] > 0) & (df['vpa'] > 0)
    
    lpa_validos = df.loc[condicao_valida_graham, 'lpa']
    vpa_validos = df.loc[condicao_valida_graham, 'vpa']
    
    if not lpa_validos.empty and not vpa_validos.empty:
        produto_para_sqrt = 22.5 * lpa_validos * vpa_validos
        vi_calculado = np.sqrt(produto_para_sqrt)
        df.loc[condicao_valida_graham, 'vi_graham'] = vi_calculado

    condicao_vi_valido = df['vi_graham'].notna() & (df['vi_graham'] != 0)
    df.loc[condicao_vi_valido, 'preco_sobre_graham'] = df.loc[condicao_vi_valido, 'cotacao'] / df.loc[condicao_vi_valido, 'vi_graham']
    return df

def preparar_X_y_para_modelo(df_com_tudo, modelo_base_path): # Adicionado modelo_base_path como argumento
    """Prepara X (features) e y (target) para o modelo, removendo colunas com nulos."""
    print("Preparando X e y para o modelo...")
    df_para_treino = df_com_tudo.dropna(subset=['rotulo_desempenho_futuro']).copy()
    
    if df_para_treino.empty:
        print("Nenhum dado restou após remover NaNs dos rótulos. O modelo não pode ser treinado.")
        return None, None, None, None

    y = df_para_treino['rotulo_desempenho_futuro'].astype(int)

    features_colunas = [
        'pl','pvp','dividend_yield','payout','margem_liquida','margem_bruta',
        'margem_ebit','margem_ebitda','ev_ebit','p_ebit',
        'p_ativo','p_cap_giro','p_ativo_circ_liq','vpa','lpa',
        'giro_ativos','roe','roic','roa','patrimonio_ativos',
        'passivos_ativos','variacao_12m','preco_sobre_graham'
    ]
    
    features_existentes = [col for col in features_colunas if col in df_para_treino.columns]
    if len(features_existentes) < len(features_colunas):
        ausentes = set(features_colunas) - set(features_existentes)
        print(f"Aviso: As seguintes colunas de features esperadas não foram encontradas no DataFrame: {list(ausentes)}. Usando apenas as existentes: {features_existentes}")
    
    if not features_existentes:
        print("Nenhuma das features esperadas foi encontrada no DataFrame. Não é possível criar X.")
        return None, None, None, None

    X = df_para_treino[features_existentes].copy()

    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    if X.empty:
        print("DataFrame X está vazio antes da imputação. Verifique a seleção de features.")
        return None, None, None, None
        
    if X.isnull().all().all():
        print("Todas as colunas de features (X) são NaN. Não é possível treinar o modelo.")
        return None, None, None, None

    print(f"Shape de X: {X.shape}, Shape de y: {y.shape}")
    return X, y, X.columns, None


def treinar_avaliar_e_salvar_modelo(X, y, X_colunas_nomes, modelo_base_path):
    """Treina, avalia e salva o modelo de classificação."""
    print("Dividindo dados em treino e teste...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("Treinando o modelo RandomForestClassifier...")
    modelo = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    modelo.fit(X_train, y_train)

    print("\nAvaliando o modelo...")
    y_pred = modelo.predict(X_test)
    y_proba = modelo.predict_proba(X_test)[:, 1]

    print("Acurácia:", accuracy_score(y_test, y_pred)) #
    print("\nMatriz de Confusão:\n", confusion_matrix(y_test, y_pred))
    print("\nRelatório de Classificação:\n", classification_report(y_test, y_pred)) #
    
    if len(np.unique(y_test)) > 1: # AUC requer mais de uma classe no y_test
        print("\nAUC-ROC:", roc_auc_score(y_test, y_proba))
    else:
        print("\nAUC-ROC não pode ser calculado (apenas uma classe presente no conjunto de teste).")

    print("\nImportância das Features (Top 15):")
    importancias = pd.Series(modelo.feature_importances_, index=X_colunas_nomes).sort_values(ascending=False)
    print(importancias.head(15))

    # Salvar o modelo
    modelo_path = os.path.join(modelo_base_path, "modelo_classificador_desempenho.pkl") # Nome diferente para o novo modelo
    os.makedirs(modelo_base_path, exist_ok=True) # Garante que o diretório 'modelo' exista
    joblib.dump(modelo, modelo_path) #
    print(f"\nModelo salvo com sucesso em {modelo_path}")
    return modelo


def executar_pipeline_classificador():
    """Executa todo o pipeline de classificação."""
    print("Iniciando pipeline do classificador...")
    
    df_bruto = carregar_dados_completos_do_banco()
    if df_bruto.empty:
        print("Pipeline encerrado devido à falha no carregamento dos dados.")
        return

    df_com_graham = calcular_features_graham_estrito(df_bruto)
    df_com_rotulos = calcular_rotulos_desempenho_futuro(df_com_graham, n_dias=10, q_inferior=0.25, q_superior=0.75)


    # Define o caminho base para salvar o modelo e o imputer
    script_dir = os.path.dirname(os.path.abspath(__file__))
    modelo_base_path = os.path.join(script_dir, "modelo")

    X, y, X_colunas_nomes, _ = preparar_X_y_para_modelo(df_com_rotulos, modelo_base_path)
    
    if X is None or y is None or X.empty or y.empty:
        print("Pipeline encerrado devido à falha na preparação de X ou y.")
        return
    
    # Define o caminho base para salvar o modelo (igual ao seu script original)
    modelo_base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo") #

    modelo_treinado = treinar_avaliar_e_salvar_modelo(X, y, X_colunas_nomes, modelo_base_path) #
    
    if modelo_treinado:
        print("\nPipeline do classificador concluído com sucesso!")
    else:
        print("\nFalha no treinamento ou salvamento do modelo.")

if __name__ == "__main__":
    executar_pipeline_classificador()