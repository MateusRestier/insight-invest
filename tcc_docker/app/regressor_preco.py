import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from labeling import calcular_rotulos_desempenho_futuro   # só para Checar colunas mínimas
from db_connection import get_connection
from classificador import calcular_features_graham_estrito  # sua função de Graham

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
        # exit()

# 1) Carrega todo o histórico do banco
def carregar_dados_do_banco():
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql_query(
            "SELECT * FROM indicadores_fundamentalistas ORDER BY acao, data_coleta;",
            conn
        )
        df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        return df
    finally:
        if conn:
            conn.close()

# 2) Calcula preco_futuro_N_dias manualmente ANTES de chamar labeling
def adicionar_preco_futuro(df, n_dias):
    df = df.copy()
    df['data_futura_alvo'] = df['data_coleta'] + pd.Timedelta(days=n_dias)

    def _por_acao(grp):
        grp = grp.sort_values('data_coleta')
        left = grp[['data_futura_alvo']].sort_values('data_futura_alvo')
        right = grp[['data_coleta', 'cotacao']]
        merged = pd.merge_asof(
            left=left, right=right,
            left_on='data_futura_alvo', right_on='data_coleta',
            direction='forward'
        )
        grp = grp.assign(preco_futuro_N_dias=merged['cotacao'].values)
        return grp

    df = df.groupby('acao', group_keys=False).apply(_por_acao)
    return df.drop(columns=['data_futura_alvo'])


# 3) Prepara X, y, dates
def preparar_dados_regressao(df, n_dias):
    # 1) Graham
    df = calcular_features_graham_estrito(df)
    # 2) Futuro
    df = adicionar_preco_futuro(df, n_dias)
    # 3) Filtra só onde target existe
    df = df.dropna(subset=['preco_futuro_N_dias']).copy()

    # 4) Escolhe features (só as que realmente existem)
    features = [
        'pl','pvp','dividend_yield','payout','margem_liquida','margem_bruta',
        'margem_ebit','margem_ebitda','ev_ebit','p_ebit',
        'p_ativo','p_cap_giro','p_ativo_circ_liq','vpa','lpa',
        'giro_ativos','roe','roic','roa','patrimonio_ativos',
        'passivos_ativos','variacao_12m','preco_sobre_graham'
    ]
    features = [f for f in features if f in df.columns]
    X = df[features].replace([np.inf, -np.inf], np.nan).dropna()
    y = df.loc[X.index, 'preco_futuro_N_dias']
    dates = df.loc[X.index, 'data_coleta']

    return X, y, dates

# 4) Treina um RandomForestRegressor com CV temporal+RandomizedSearch
def treinar_regressor(X_train, y_train):
    tscv = TimeSeriesSplit(n_splits=5)
    param_dist = {
        'n_estimators':    [100, 200, 300],
        'max_depth':       [None, 10, 20],
        'min_samples_leaf':[1, 2, 5],
        'max_features':    ['sqrt','log2',0.5]
    }
    search = RandomizedSearchCV(
        RandomForestRegressor(random_state=42),
        param_distributions=param_dist,
        n_iter=15, cv=tscv,
        scoring='neg_mean_absolute_error',
        n_jobs=-1, random_state=42, verbose=1
    )
    search.fit(X_train, y_train)
    print("🔑 Melhores parâmetros:", search.best_params_)
    return search.best_estimator_

# 5) Pipeline completo
def executar_pipeline_regressor(n_dias=10):
    # 1) Carrega tudo
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM indicadores_fundamentalistas", conn)
    conn.close()
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])

    # 2) Prepara X, y e dates
    X, y, dates = preparar_dados_regressao(df, n_dias)

    # 3) Hold-out: últimos n_dias
    cutoff = dates.max() - pd.Timedelta(days=n_dias)
    mask_train = dates <= cutoff
    mask_test  = dates  > cutoff
    X_train, y_train = X[mask_train], y[mask_train]
    X_test,  y_test  = X[mask_test],  y[mask_test]

    # 4) Treino básico (pode trocar por RandomizedSearchCV se quiser tunar)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    # 5) Métricas
    print("MAE:", mean_absolute_error(y_test, preds))
    print("MSE:", mean_squared_error(y_test, preds))
    print("R² :", r2_score(y_test, preds))

    # 6) Comparação detalhada
    comp = pd.DataFrame({
        'data': dates[mask_test],
        'real': y_test,
        'predito': preds
    }).sort_values('data')
    comp['erro_pct'] = (comp['predito'] - comp['real'])/comp['real']*100
    print(comp.head(10))
    print("\nErro % (descrição):\n", comp['erro_pct'].describe())

    return model, comp

if __name__ == "__main__":
    executar_pipeline_regressor(n_dias=10)
