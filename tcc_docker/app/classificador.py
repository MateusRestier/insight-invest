import os, joblib, pandas as pd, numpy as np, psycopg2
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, roc_auc_score
from sklearn.impute import SimpleImputer
from labeling import calcular_rotulos_desempenho_futuro

# Tenta importar do local padrão do seu projeto TCC
try:
    from app.db_connection import get_connection
except ImportError:
    try:
        from db_connection import get_connection 
        print("Importou 'get_connection' do diretório atual.") 
    except ImportError as e:
        print(f"Erro ao importar 'get_connection': {e}")
        print("Certifique-se de que db_connection.py está acessível e as variáveis de ambiente do DB estão configuradas.")
        exit()


def carregar_dados_completos_do_banco():
    """Carrega TODOS os dados da tabela indicadores_fundamentalistas do banco de dados."""
    conn = None
    try:
        conn = get_connection() 
        query = "SELECT * FROM indicadores_fundamentalistas ORDER BY acao, data_coleta;"
        df = pd.read_sql_query(query, conn) 
        if 'data_coleta' in df.columns:
            df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        print(f"Todos os indicadores carregados do banco! Shape: {df.shape}")
        return df
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao carregar dados do banco: {error}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close() 

# NOVO: Função para agregar dados e reduzir redundância
def agregar_dados_temporalmente(df, periodo='W'):
    """
    Agrega os dados diários em períodos maiores (semanal 'W' ou mensal 'M').
    Isso reduz a redundância e o ruído dos dados diários.
    
    Args:
        df (pd.DataFrame): O DataFrame com os dados diários.
        periodo (str): A frequência da agregação ('W' para semanal, 'M' para mensal).
    
    Returns:
        pd.DataFrame: O DataFrame com os dados agregados.
    """
    if 'data_coleta' not in df.columns or df.empty:
        return df
        
    print(f"Agregando dados para o período: {periodo} (Semanal) ...")
    
    # Define 'data_coleta' como índice para poder agrupar por tempo
    df_agregado = df.set_index('data_coleta')
    
    # Agrupa por ação e pelo período de tempo, calculando a média dos indicadores
    # Usamos .mean() para suavizar os valores ao longo da semana
    # numeric_only=True é importante para ignorar colunas não numéricas que não podem ser agregadas
    df_agregado = df_agregado.groupby(['acao', pd.Grouper(freq=periodo)]).mean(numeric_only=True)
    
    # Remove linhas que possam ter ficado totalmente vazias após a agregação
    df_agregado.dropna(how='all', inplace=True)
    
    # Reseta o índice para que 'acao' e 'data_coleta' voltem a ser colunas
    df_agregado = df_agregado.reset_index()
    
    print(f"Shape após agregação: {df_agregado.shape}")
    return df_agregado


def calcular_features_graham_estrito(df_input):
    """
    Calcula o VI de Graham e a feature Preco_Sobre_Graham de forma estrita.
    (Esta função permanece a mesma)
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

# ALTERADO: A função agora retorna 5 valores mesmo em caso de falha
def preparar_X_y_para_modelo(df_com_tudo, modelo_base_path):
    """Prepara X (features) e y (target) para o modelo e salva o imputer."""
    print("Preparando X e y para o modelo...")
    df_com_tudo = df_com_tudo.sort_values(by='data_coleta').reset_index(drop=True)

    df_para_treino = df_com_tudo.dropna(subset=['rotulo_desempenho_futuro']).copy()
    
    if df_para_treino.empty:
        print("Nenhum dado restou após remover NaNs dos rótulos. O modelo não pode ser treinado.")
        # ALTERADO: Retornar 5 valores 'None' para evitar o ValueError
        return None, None, None, None, None 

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
    X = df_para_treino[features_existentes].copy()
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    if X.empty:
        print("DataFrame X está vazio.")
        return None, None, None, None, None
        
    imputer = SimpleImputer(strategy='median')
    X_imputado = imputer.fit_transform(X) 
    X = pd.DataFrame(X_imputado, columns=X.columns, index=X.index)
    
    os.makedirs(modelo_base_path, exist_ok=True) 
    imputer_path = os.path.join(modelo_base_path, "imputer.pkl")
    try:
        joblib.dump(imputer, imputer_path)
        print(f"Imputer salvo com sucesso em {imputer_path}")
    except Exception as e:
        print(f"Erro ao salvar o imputer: {e}")
    
    print(f"Shape de X (após imputação): {X.shape}, Shape de y: {y.shape}")
    return X, y, X.columns, imputer, df_para_treino

# ALTERADO: Substituição do train_test_split aleatório por uma divisão temporal
def treinar_avaliar_e_salvar_modelo(X, y, X_colunas_nomes, df_para_treino, modelo_base_path):
    """Treina, avalia (com divisão temporal) e salva o modelo de classificação."""
    print("Dividindo dados em treino e teste (Divisão Temporal)...")
    
    # Garante que os dados estejam alinhados e ordenados por data
    dados_completos = pd.concat([X, y, df_para_treino['data_coleta']], axis=1).sort_values(by='data_coleta')
    
    # Recalcula X e y a partir do DataFrame ordenado para garantir consistência
    X_ordenado = dados_completos[X_colunas_nomes]
    y_ordenado = dados_completos['rotulo_desempenho_futuro']

    # Define o ponto de corte (80% dos dados para treino, 20% para teste)
    split_ratio = 0.8
    split_index = int(len(X_ordenado) * split_ratio)

    X_train = X_ordenado.iloc[:split_index]
    X_test = X_ordenado.iloc[split_index:]
    y_train = y_ordenado.iloc[:split_index]
    y_test = y_ordenado.iloc[split_index:]

    print(f"Tamanho do treino: {len(X_train)} amostras")
    print(f"Tamanho do teste: {len(X_test)} amostras")
    
    print("Treinando o modelo RandomForestClassifier...")
    modelo = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    modelo.fit(X_train, y_train)

    print("\nAvaliando o modelo...")
    y_pred = modelo.predict(X_test)
    y_proba = modelo.predict_proba(X_test)[:, 1]

    print("Acurácia:", accuracy_score(y_test, y_pred))
    print("\nMatriz de Confusão:\n", confusion_matrix(y_test, y_pred))
    print("\nRelatório de Classificação:\n", classification_report(y_test, y_pred))
    
    if len(np.unique(y_test)) > 1:
        print("\nAUC-ROC:", roc_auc_score(y_test, y_proba))
    else:
        print("\nAUC-ROC não pode ser calculado (apenas uma classe presente no conjunto de teste).")

    print("\nImportância das Features (Top 15):")
    importancias = pd.Series(modelo.feature_importances_, index=X_colunas_nomes).sort_values(ascending=False)
    print(importancias.head(15))

    modelo_path = os.path.join(modelo_base_path, "modelo_classificador_desempenho.pkl")
    os.makedirs(modelo_base_path, exist_ok=True)
    joblib.dump(modelo, modelo_path)
    print(f"\nModelo salvo com sucesso em {modelo_path}")
    return modelo


def executar_pipeline_classificador():
    """Executa todo o pipeline de classificação, agora com agregação e divisão temporal."""
    print("Iniciando pipeline do classificador...")
    
    df_bruto = carregar_dados_completos_do_banco()
    if df_bruto.empty:
        print("Pipeline encerrado devido à falha no carregamento dos dados.")
        return

    # Idealmente, com mais dados, você poderá aumentar a janela de tempo
    # janela_dias = 84 # Exemplo: ~3 meses

    # Por enquanto, mantemos uma janela curta para testes
    janela_dias = 14 
    
    df_agregado = agregar_dados_temporalmente(df_bruto, periodo='W')
    df_com_graham = calcular_features_graham_estrito(df_agregado)

    print(f"Calculando rótulos de desempenho futuro com janela de {janela_dias} dias...")
    df_com_rotulos = calcular_rotulos_desempenho_futuro(df_com_graham, n_dias=janela_dias, q_inferior=0.25, q_superior=0.75)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    modelo_base_path = os.path.join(script_dir, "modelo")

    X, y, X_colunas_nomes, imputer_ajustado, df_para_treino = preparar_X_y_para_modelo(df_com_rotulos, modelo_base_path)
    
    if X is None or y is None:
        print("Pipeline encerrado devido à falha na preparação de X e y (dados de rótulo insuficientes).")
        return
    
    modelo_treinado = treinar_avaliar_e_salvar_modelo(X, y, X_colunas_nomes, df_para_treino, modelo_base_path)
    
    if modelo_treinado:
        print("\nPipeline do classificador concluído com sucesso!")
    else:
        print("\nFalha no treinamento ou salvamento do modelo.")

if __name__ == "__main__":
    executar_pipeline_classificador()