import os, joblib, pandas as pd, numpy as np, psycopg2
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
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

def preparar_X_y_para_modelo(df_com_tudo, modelo_base_path):
    """Prepara X (features), y (target) e dates (data_coleta) para o modelo, removendo colunas com nulos."""
    print("Preparando X, y e dates para o modelo...")
    # Filtra apenas linhas com rótulo definido
    df_para_treino = df_com_tudo.dropna(subset=['rotulo_desempenho_futuro']).copy()
    if df_para_treino.empty:
        print("Nenhum dado restou após remover NaNs dos rótulos. O modelo não pode ser treinado.")
        return None, None, None, None, None

    # Extrai y e dates
    y = df_para_treino['rotulo_desempenho_futuro'].astype(int)
    dates = df_para_treino['data_coleta']

    # Define as features a usar
    features_colunas = [
        'pl','pvp','dividend_yield','payout','margem_liquida','margem_bruta',
        'margem_ebit','margem_ebitda','ev_ebit','p_ebit',
        'p_ativo','p_cap_giro','p_ativo_circ_liq','vpa','lpa',
        'giro_ativos','roe','roic','roa','patrimonio_ativos',
        'passivos_ativos','variacao_12m','preco_sobre_graham', 'fund_bad'
    ]
    features_existentes = [col for col in features_colunas if col in df_para_treino.columns]
    if len(features_existentes) < len(features_colunas):
        ausentes = set(features_colunas) - set(features_existentes)
        print(f"Aviso: colunas ausentes: {list(ausentes)}. Usando: {features_existentes}")
    if not features_existentes:
        print("Nenhuma das features esperadas foi encontrada. Não é possível criar X.")
        return None, None, None, None, None

    # Constrói X e trata infinitos
    X = df_para_treino[features_existentes].copy()
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    if X.empty or X.isnull().all().all():
        print("X está vazio ou todas as features são NaN. Não é possível treinar o modelo.")
        return None, None, None, None, None

    print(f"Shape de X: {X.shape}, Shape de y: {y.shape}")
    # Retorna também a série de datas alinhada a X.index
    return X, y, X.columns, None, dates


def treinar_avaliar_e_salvar_modelo(X_train, y_train, X_colunas_nomes, modelo_base_path):
    """Tuna hiperparâmetros via RandomizedSearchCV com TimeSeriesSplit e salva o modelo."""
    print("⚙️  Iniciando RandomizedSearchCV com TimeSeriesSplit…")
    tscv = TimeSeriesSplit(n_splits=5)

    param_dist = { # Serve para fazer uma busca aleatória de hiperparâmetros, e ver quais são os melhores
        'n_estimators': [50, 100, 200, 300, 400, 500],
        'max_depth': [None, 5, 10, 20, 30],
        'min_samples_leaf': [1, 2, 5],
        'max_features': ['sqrt', 'log2', 0.3, 0.5, 0.7],
        'class_weight': ['balanced', None]
    }

    search = RandomizedSearchCV(
        RandomForestClassifier(random_state=42),
        param_distributions=param_dist,
        n_iter=20, cv=tscv, scoring='roc_auc',
        n_jobs=-1, verbose=2, random_state=42
    )
    search.fit(X_train, y_train)

    print("\n🔑 Melhores parâmetros encontrados:", search.best_params_)
    print(f"🏆 Melhor AUC-ROC (CV): {search.best_score_:.4f}")

    modelo = search.best_estimator_

    # Importância das features
    importancias = pd.Series(modelo.feature_importances_, index=X_colunas_nomes)\
                      .sort_values(ascending=False)
    print("\nImportância das Features (Top 23):")
    print(importancias.head(23))

    # Salvar o modelo
    modelo_path = os.path.join(modelo_base_path, "modelo_classificador_desempenho.pkl")
    os.makedirs(modelo_base_path, exist_ok=True)
    joblib.dump(modelo, modelo_path)
    print(f"\n✅ Modelo final (tuneado) salvo em {modelo_path}")

    return modelo

def executar_pipeline_classificador():
    """Executa todo o pipeline de classificação, com split temporal hold-out antes do tuning."""
    print("Iniciando pipeline do classificador…")
    
    # 1) Carrega dados
    df_bruto = carregar_dados_completos_do_banco()
    if df_bruto.empty:
        print("Pipeline encerrado devido à falha no carregamento dos dados.")
        return

    # 2) Calcula Graham e rótulos
    df_com_graham = calcular_features_graham_estrito(df_bruto)
    df_com_rotulos = calcular_rotulos_desempenho_futuro(df_com_graham,n_dias=10, q_inferior=0.25, q_superior=0.75)

    # Qualquer ação com PL ou ROE negativos vira rótulo 0
    mask_bad = (df_com_rotulos['pl'] <= 0) | (df_com_rotulos['roe'] <= 0)
    df_com_rotulos['fund_bad'] = mask_bad.astype(int)
    df_com_rotulos.loc[mask_bad, 'rotulo_desempenho_futuro'] = 0
    


    # 3) Monta X, y e dates
    script_dir = os.path.dirname(os.path.abspath(__file__))
    modelo_base_path = os.path.join(script_dir, "modelo")
    X, y, X_colunas_nomes, _, dates = preparar_X_y_para_modelo(df_com_rotulos, modelo_base_path)

    if X is None or y is None or X.empty or y.empty:
        print("Pipeline encerrado devido à falha na preparação de X ou y.")
        return

    # 4) Hold-out temporal: últimos 20% das datas → teste
    limite = dates.quantile(0.80)
    mask_train = dates <= limite
    mask_hold  = dates  > limite

    X_train, y_train = X[mask_train], y[mask_train]
    X_hold,  y_hold  = X[mask_hold],  y[mask_hold]

    # 5) Treina e faz cross-validation temporal só no treino
    modelo = treinar_avaliar_e_salvar_modelo(
        X_train, y_train,
        X_colunas_nomes,
        modelo_base_path
    )

    # 6) Avalia no hold-out que ficou de fora de todo o processo de tuning/refit
    print("\n📊 Avaliação final no hold-out (20% mais recentes):")
    y_pred = modelo.predict(X_hold)
    y_proba = modelo.predict_proba(X_hold)[:, 1]

    print("Acurácia (hold-out):", accuracy_score(y_hold, y_pred))
    print("\nMatriz de Confusão (hold-out):\n", confusion_matrix(y_hold, y_pred))
    print("\nRelatório de Classificação (hold-out):\n", classification_report(y_hold, y_pred))
    print("\nAUC-ROC (hold-out):", roc_auc_score(y_hold, y_proba))

    print("\nPipeline do classificador concluído com sucesso!")


if __name__ == "__main__":
    executar_pipeline_classificador()