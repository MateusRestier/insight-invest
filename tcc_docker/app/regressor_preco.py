import pandas as pd, numpy as np
from datetime import datetime, timedelta, date
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

def obter_data_calculo_maxima():
    conn = get_connection()
    df = pd.read_sql_query("SELECT MAX(data_coleta) AS ultima_data FROM indicadores_fundamentalistas", conn)
    conn.close()

    ultima_data = pd.to_datetime(df['ultima_data'].iloc[0]).date()
    print(f"\n📅 Data máxima permitida para data_calculo (última data disponível no banco): {ultima_data.strftime('%Y-%m-%d')}")
    return ultima_data


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

    '''# Diagnóstico: verificar % de NaN em cada feature
    print("\n---- Diagnóstico de NaNs por Feature (antes do dropna) ----")
    print(df[features].isnull().mean().sort_values(ascending=False) * 100)'''

    X = df[features].replace([np.inf, -np.inf], np.nan).dropna()
    y = df.loc[X.index, 'preco_futuro_N_dias']
    dates = df.loc[X.index, 'data_coleta']
    acoes = df.loc[X.index, 'acao']

    return X, y, dates, acoes

# 4) Salvar no banco
def salvar_resultados_no_banco(comp, data_calculo):
    conn = None
    try:
        # Remover duplicatas por ação + data_previsao
        comp_filtrado = comp.sort_values('data').groupby(['acao', 'data'], as_index=False).last()

        conn = get_connection()
        cur = conn.cursor()

        for idx, row in comp_filtrado.iterrows():
            sql = """
                INSERT INTO resultados_precos (acao, data_calculo, data_previsao, preco_previsto)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (acao, data_previsao) DO UPDATE SET
                    preco_previsto = EXCLUDED.preco_previsto,
                    data_calculo = EXCLUDED.data_calculo
            """
            values = (
                row['acao'],
                data_calculo,
                row['data'],  # AQUI É A DATA PREVISTA (do próprio hold-out)
                float(row['predito'])
            )
            cur.execute(sql, values)

        conn.commit()
        print(f"\n✅ Resultados salvos/atualizados na tabela resultados_precos. Total de ações únicas inseridas: {comp['acao'].nunique()}")


    except Exception as e:
        print(f"❌ Erro ao inserir resultados no banco: {e}")
    finally:
        if conn:
            conn.close()



# 5) Pipeline completo
def executar_pipeline_regressor(n_dias=10, data_calculo=None):
    if data_calculo is None:
        data_calculo = date.today()

    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM indicadores_fundamentalistas", conn)
    conn.close()
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])

    X, y, dates, acoes = preparar_dados_regressao(df, n_dias)

    # Corte de treino limitado ao data_calculo
    cutoff = pd.to_datetime(data_calculo)
    mask_train = dates <= cutoff
    mask_test  = dates > cutoff

    # Se a data_calculo for maior que a última data real do banco
    ultima_data_banco = df['data_coleta'].max().date()
    if data_calculo > ultima_data_banco:
        print(f"\n⚠️ Aviso: data_calculo ({data_calculo}) é maior que a última data do banco ({ultima_data_banco}).")
        mask_train = dates <= ultima_data_banco
        mask_test = pd.Series([False] * len(dates), index=dates.index)

    X_train, y_train = X[mask_train], y[mask_train]
    X_test,  y_test  = X[mask_test],  y[mask_test]
    acoes_test       = acoes[mask_test]
    dates_test       = dates[mask_test]

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    if X_test.empty:
        print("\n⚠️ Não existem datas futuras no banco para teste. Fazendo previsão futura manual...")

        future_date = data_calculo + timedelta(days=n_dias)

        ultimas_linhas_por_acao = X_train.groupby(acoes.loc[X_train.index]).tail(1)
        preds = model.predict(ultimas_linhas_por_acao)

        comp = pd.DataFrame({
            'acao': acoes.loc[ultimas_linhas_por_acao.index].values,
            'data': [future_date] * len(ultimas_linhas_por_acao),
            'real': [None] * len(ultimas_linhas_por_acao),
            'predito': preds,
            'erro_pct': [None] * len(ultimas_linhas_por_acao)
        }).sort_values('acao')
    else:
        future_date = data_calculo + timedelta(days=n_dias)
        preds = model.predict(X_test)
        comp = pd.DataFrame({
            'acao': acoes_test.values,
            'data': [future_date] * len(acoes_test),  # Forçando data_previsao igual para todas as linhas
            'real': y_test.values,
            'predito': preds
        }).sort_values('acao')
        comp['erro_pct'] = (comp['predito'] - comp['real']) / comp['real'] * 100
        comp = comp.drop_duplicates(subset=['acao', 'data'])

    print("\n📊 Métricas de desempenho no treino:")
    print(f"MAE: {mean_absolute_error(y_train, model.predict(X_train)):.4f}")
    print(f"MSE: {mean_squared_error(y_train, model.predict(X_train)):.4f}")
    print(f"R² : {r2_score(y_train, model.predict(X_train)):.4f}")

    salvar_resultados_no_banco(comp, data_calculo)
    return model, comp


if __name__ == "__main__":
    try:
        n_dias = 10
        n_dias = int(input("Digite o número de dias futuros que deseja prever (ex: 10): "))
    except ValueError:
        print("Valor inválido para n_dias. Encerrando...")
        exit()

    data_maxima = obter_data_calculo_maxima()

    print("\nEscolha uma opção:")
    print(f"1 - Prever {n_dias} dias no futuro a partir de HOJE")
    print(f"2 - Prever {n_dias} dias no futuro a partir de uma data manual (X)")
    print(f"3 - Prever {n_dias} dias no futuro para um intervalo de datas_calculo (de X até Y)")

    escolha = 1
    escolha = input("\nDigite 1, 2 ou 3: ").strip()

    if escolha == "1":
        data_calculo = date.today()
        if data_calculo > data_maxima:
            print(f"\n❌ ERRO: data_calculo não pode ser maior que {data_maxima}. Encerrando...")
            exit()
        print(f"\n✅ Iniciando pipeline para data_calculo = {data_calculo} e n_dias = {n_dias}...\n")
        executar_pipeline_regressor(n_dias=n_dias, data_calculo=data_calculo)

    elif escolha == "2":
        data_input = input(f"Digite a data_calculo desejada (AAAA-MM-DD) (máximo permitido: {data_maxima}): ")
        try:
            data_calculo = datetime.strptime(data_input, "%Y-%m-%d").date()
            if data_calculo > data_maxima:
                print(f"\n❌ ERRO: A data_calculo não pode ser maior que {data_maxima}. Encerrando...")
                exit()
        except ValueError:
            print("\n❌ ERRO: Data inválida. Use o formato AAAA-MM-DD. Encerrando...")
            exit()
        print(f"\n✅ Iniciando pipeline para data_calculo = {data_calculo} e n_dias = {n_dias}...\n")
        executar_pipeline_regressor(n_dias=n_dias, data_calculo=data_calculo)

    elif escolha == "3":
        data_inicio_input = input(f"Digite a data inicial do intervalo (AAAA-MM-DD) (máximo permitido: {data_maxima}): ")
        data_fim_input = input(f"Digite a data final do intervalo (AAAA-MM-DD) (máximo permitido: {data_maxima}): ")

        try:
            data_inicio = datetime.strptime(data_inicio_input, "%Y-%m-%d").date()
            data_fim = datetime.strptime(data_fim_input, "%Y-%m-%d").date()

            if data_inicio > data_fim:
                print("\n❌ ERRO: A data inicial não pode ser depois da data final. Encerrando...")
                exit()
            if data_fim > data_maxima:
                print(f"\n❌ ERRO: A data final não pode ser maior que {data_maxima}. Encerrando...")
                exit()

            print(f"\n✅ Iniciando previsão de {n_dias} dias para o intervalo de datas: {data_inicio} até {data_fim}...\n")

            data_atual = data_inicio
            while data_atual <= data_fim:
                print(f"\n👉 Executando previsão para data_calculo = {data_atual}...")
                executar_pipeline_regressor(n_dias=n_dias, data_calculo=data_atual)
                data_atual += timedelta(days=1)

        except ValueError:
            print("\n❌ ERRO: Datas inválidas. Use o formato correto AAAA-MM-DD. Encerrando...")
            exit()

    else:
        print("\n❌ Opção inválida. Encerrando...")
        exit()
