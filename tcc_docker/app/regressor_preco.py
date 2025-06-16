import pandas as pd, numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from db_connection import get_connection
from classificador import calcular_features_graham_estrito

# 1) Carrega o histórico
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

# 2) Calcula preco_futuro_N_dias
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
    df = calcular_features_graham_estrito(df)
    df = adicionar_preco_futuro(df, n_dias)
    df = df.dropna(subset=['preco_futuro_N_dias']).copy()

    features = [
        'pl','pvp','dividend_yield','payout','margem_liquida','margem_bruta',
        'margem_ebit','margem_ebitda','ev_ebit','p_ebit',
        'p_ativo','p_cap_giro','p_ativo_circ_liq','vpa','lpa',
        'giro_ativos','roe','roic','roa','patrimonio_ativos',
        'passivos_ativos','variacao_12m'
    ]
    features = [f for f in features if f in df.columns]

    # Diagnóstico: verificar % de NaN em cada feature
    print("\n---- Diagnóstico de NaNs por Feature (antes do dropna) ----")
    print(df[features].isnull().mean().sort_values(ascending=False) * 100)

    X = df[features].replace([np.inf, -np.inf], np.nan).dropna()
    y = df.loc[X.index, 'preco_futuro_N_dias']
    dates = df.loc[X.index, 'data_coleta']
    acoes = df.loc[X.index, 'acao']

    return X, y, dates, acoes

# 4) Salvar no banco
def salvar_resultados_no_banco(comp, n_dias):
    conn = None
    try:
        # Para cada ação, manter apenas a última linha (última data disponível no hold-out)
        comp_filtrado = comp.sort_values('data').groupby('acao', as_index=False).last()

        conn = get_connection()
        cur = conn.cursor()

        for idx, row in comp_filtrado.iterrows():
            sql = """
                INSERT INTO resultados_precos (acao, data_previsao, preco_real, preco_previsto, erro_pct, data_coleta)
                VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)
            """
            values = (
                row['acao'],
                row['data'] + pd.Timedelta(days=n_dias),
                float(row['real']),
                float(row['predito']),
                float(row['erro_pct']) if pd.notna(row['erro_pct']) else None
            )
            cur.execute(sql, values)

        conn.commit()
        print(f"\n✅ Resultados salvos na tabela resultados_precos. Total de ações inseridas: {len(comp_filtrado)}")

    except Exception as e:
        print(f"❌ Erro ao inserir resultados no banco: {e}")
    finally:
        if conn:
            conn.close()

# 5) Pipeline completo
def executar_pipeline_regressor(n_dias):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM indicadores_fundamentalistas", conn)
    conn.close()
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])

    X, y, dates, acoes = preparar_dados_regressao(df, n_dias)

    cutoff = dates.max() - pd.Timedelta(days=n_dias)
    mask_train = dates <= cutoff
    mask_test  = dates  > cutoff

    X_train, y_train = X[mask_train], y[mask_train]
    X_test,  y_test  = X[mask_test],  y[mask_test]
    acoes_test       = acoes[mask_test]
    dates_test       = dates[mask_test]

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    print("MAE:", mean_absolute_error(y_test, preds))
    print("MSE:", mean_squared_error(y_test, preds))
    print("R² :", r2_score(y_test, preds))

    comp = pd.DataFrame({
        'acao': acoes_test.values,
        'data': dates_test.values,
        'real': y_test.values,
        'predito': preds
    }).sort_values('data')

    comp['erro_pct'] = (comp['predito'] - comp['real']) / comp['real'] * 100

    # Remove duplicadas por ação + data
    comp = comp.drop_duplicates(subset=['acao', 'data'])

    print(comp.head(10))
    print("\nErro % (descrição):\n", comp['erro_pct'].describe())

    # Nova parte: salvar no banco
    salvar_resultados_no_banco(comp, n_dias)

    return model, comp

if __name__ == "__main__":
    executar_pipeline_regressor(n_dias=10)