import os
import joblib
import pandas as pd
import numpy as np
import psycopg2 # Necessário para get_connection
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, roc_auc_score
from sklearn.impute import SimpleImputer

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


def calcular_rotulos_desempenho_futuro(df_input, n_dias=10, q_inferior=0.25, q_superior=0.75):
    """
    Calcula os rótulos de desempenho futuro relativo.
    1: Top X% (definido por q_superior)
    0: Bottom Y% (definido por q_inferior)
    NaN: Meio (será descartado)
    """
    df = df_input.copy()
    if not isinstance(df.index, pd.MultiIndex) and not df.empty:
        if 'data_coleta' in df.columns:
             df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        df = df.sort_values(by=['acao', 'data_coleta'])

    print(f"Calculando rótulos de desempenho para N={n_dias} dias, q_inf={q_inferior}, q_sup={q_superior}")
    df['preco_futuro_N_dias'] = df.groupby('acao')['cotacao'].shift(-n_dias)
    df['retorno_futuro_N_dias'] = np.where(
        df['cotacao'] > 0,
        (df['preco_futuro_N_dias'] - df['cotacao']) / df['cotacao'],
        np.nan
    )
    df['rotulo_desempenho_futuro'] = np.nan
    datas_com_retorno_valido = df.dropna(subset=['retorno_futuro_N_dias'])['data_coleta'].unique()
    
    if not datas_com_retorno_valido.any():
        print("Nenhuma data com retorno futuro válido encontrada para rotulagem. Verifique o tamanho do dataset e N.")
        return df

    for data_atual in datas_com_retorno_valido:
        dia_df = df[(df['data_coleta'] == data_atual) & (df['retorno_futuro_N_dias'].notna())].copy()
        if dia_df.empty:
            continue
        quantil_inf = dia_df['retorno_futuro_N_dias'].quantile(q_inferior)
        quantil_sup = dia_df['retorno_futuro_N_dias'].quantile(q_superior)
        indices_dia = dia_df.index
        df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] <= quantil_inf], 'rotulo_desempenho_futuro'] = 0
        df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] >= quantil_sup], 'rotulo_desempenho_futuro'] = 1
    
    print("Contagem de rótulos de desempenho futuro:")
    print(df['rotulo_desempenho_futuro'].value_counts(dropna=False))
    return df


def preparar_X_y_para_modelo(df_com_tudo, modelo_base_path): # Adicionado modelo_base_path como argumento
    """Prepara X (features) e y (target) para o modelo e salva o imputer."""
    print("Preparando X e y para o modelo...")
    df_para_treino = df_com_tudo.dropna(subset=['rotulo_desempenho_futuro']).copy()
    
    if df_para_treino.empty:
        print("Nenhum dado restou após remover NaNs dos rótulos. O modelo não pode ser treinado.")
        return None, None, None, None # Retornar None para o imputer também

    y = df_para_treino['rotulo_desempenho_futuro'].astype(int)

    features_colunas = [
        'pl', 'psr', 'pvp', 'dividend_yield', 'payout', 'margem_liquida', 'margem_bruta',
        'margem_ebit', 'margem_ebitda', 'ev_ebitda', 'ev_ebit', 'p_ebitda', 'p_ebit',
        'p_ativo', 'p_cap_giro', 'p_ativo_circ_liq', 'vpa', 'lpa',
        'giro_ativos', 'roe', 'roic', 'roa', 'div_liq_patrimonio', 'div_liq_ebitda',
        'div_liq_ebit', 'div_bruta_patrimonio', 'patrimonio_ativos', 'passivos_ativos',
        'liquidez_corrente', 'variacao_12m',
        'preco_sobre_graham'
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

    imputer = SimpleImputer(strategy='median')
    # Ajustar o imputer APENAS nos dados que serão usados para TREINAR o modelo (X)
    # Se você faz o train_test_split ANTES da imputação, ajuste o imputer no X_train
    # e transforme tanto X_train quanto X_test.
    # Assumindo por enquanto que X aqui é o conjunto completo que será dividido depois:
    X_imputado = imputer.fit_transform(X) 
    X = pd.DataFrame(X_imputado, columns=X.columns, index=X.index)
    
    # Salvar o imputer ajustado
    # Garante que o diretório 'modelo' exista (modelo_base_path é o diretório 'modelo')
    os.makedirs(modelo_base_path, exist_ok=True) 
    imputer_path = os.path.join(modelo_base_path, "imputer.pkl")
    try:
        joblib.dump(imputer, imputer_path)
        print(f"Imputer salvo com sucesso em {imputer_path}")
    except Exception as e:
        print(f"Erro ao salvar o imputer: {e}")
        # Você pode decidir se quer interromper ou continuar mesmo se o imputer não for salvo
    
    print(f"Shape de X (após imputação): {X.shape}, Shape de y: {y.shape}")
    return X, y, X.columns, imputer # Retornar o imputer também, caso precise dele na sequência


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

    X, y, X_colunas_nomes, imputer_ajustado = preparar_X_y_para_modelo(df_com_rotulos, modelo_base_path)
    
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
    # Configurar variáveis de ambiente para teste local, se necessário.
    # os.environ["DB_HOST"] = "localhost"
    # os.environ["DB_NAME"] = "stocks"
    # os.environ["DB_USER"] = "user"
    # os.environ["DB_PASS"] = "password"
    # os.environ["DB_PORT"] = "5432"
    executar_pipeline_classificador()