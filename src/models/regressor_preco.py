import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd, numpy as np
from datetime import datetime, timedelta, date
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from src.core.db_connection import get_connection
from src.models.classificador import calcular_features_graham_estrito

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
        # Ordena e remove duplicatas por ação + data_previsao
        comp_filtrado = (
            comp
            .sort_values('data_previsao')
            .groupby(['acao', 'data_previsao'], as_index=False)
            .last()
        )

        conn = get_connection()
        cur = conn.cursor()

        for _, row in comp_filtrado.iterrows():
            sql = """
                INSERT INTO resultados_precos (acao, data_calculo, data_previsao, preco_previsto)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (acao, data_previsao) DO UPDATE SET
                    preco_previsto = EXCLUDED.preco_previsto,
                    data_calculo   = EXCLUDED.data_calculo
            """
            values = (
                row['acao'],
                data_calculo,
                row['data_previsao'],   # agora usa data_previsao
                float(row['preco_previsto'])  # agora usa preco_previsto
            )
            cur.execute(sql, values)

        conn.commit()
        print(f"\n✅ Resultados salvos/atualizados. Ações únicas: {comp['acao'].nunique()}")

    except Exception as e:
        print(f"❌ Erro ao inserir resultados no banco: {e}")
    finally:
        if conn:
            conn.close()


# 5) Pipeline completo
def executar_pipeline_regressor(
    n_dias: int = 10,
    data_calculo: date | None = None,
    save_to_db: bool = True,
    tickers: list[str] | None = None
) -> tuple[RandomForestRegressor, pd.DataFrame]:
    """
    Executa o pipeline de regressão para previsão de preços.
    Args:
        n_dias: número de dias futuros para prever.
        data_calculo: data base para cálculo (se None, usa hoje).
        save_to_db: se True, persiste em resultados_precos.
        tickers: lista de ações para filtrar o resultado (ou None para todas).
    Returns:
        model: RandomForestRegressor treinado.
        comp: DataFrame com colunas ['acao','data_previsao','real','preco_previsto','erro_pct'].
    """
    if data_calculo is None:
        data_calculo = date.today()

    # 1) Carrega histórico de indicadores
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM indicadores_fundamentalistas", conn)
    conn.close()
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])

    # 2) Prepara X, y, datas e tickers
    X, y, dates, acoes = preparar_dados_regressao(df, n_dias)

    # 3) Define máscaras de treino/teste com base em data_calculo
    ultima_real_date = df['data_coleta'].max().date()
    if data_calculo > ultima_real_date:
        print(f"⚠️ data_calculo ({data_calculo}) > última data no banco ({ultima_real_date}); ajustando treino.")
        ultima_ts = pd.to_datetime(ultima_real_date)
        mask_train = dates <= ultima_ts
        mask_test  = pd.Series(False, index=dates.index)
    else:
        cutoff     = pd.to_datetime(data_calculo)
        mask_train = dates < cutoff
        mask_test  = dates == cutoff

    X_train, y_train = X[mask_train], y[mask_train]
    X_test,  y_test  = X[mask_test],  y[mask_test]
    acoes_test       = acoes[mask_test]

    # 4) Treina o modelo
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # 5) Gera previsões
    future_date = data_calculo + timedelta(days=n_dias)
    if X_test.empty:
        print("⚠️ Sem dados futuros para teste; gerando previsão manual.")
        ultimos = X_train.groupby(acoes.loc[X_train.index]).tail(1)
        preds   = model.predict(ultimos)
        comp = pd.DataFrame({
            'acao':   acoes.loc[ultimos.index].values,
            'data':   [future_date] * len(ultimos),
            'real':   [None]            * len(ultimos),
            'predito': preds
        })
        comp['erro_pct'] = None
    else:
        preds = model.predict(X_test)
        comp = pd.DataFrame({
            'acao':    acoes_test.values,
            'data':    [future_date]      * len(acoes_test),
            'real':    y_test.values,
            'predito': preds
        })
        comp['erro_pct'] = (comp['predito'] - comp['real']) / comp['real'] * 100

    comp = comp.drop_duplicates(subset=['acao', 'data']).sort_values('acao')

    # 6) Imprime métricas de treino
    print("📊 Métricas de treino:")
    print(f"MAE: {mean_absolute_error(y_train, model.predict(X_train)):.4f}")
    print(f"MSE: {mean_squared_error(y_train, model.predict(X_train)):.4f}")
    print(f"R² : {r2_score(y_train, model.predict(X_train)):.4f}")

    # 7) Renomeia colunas para uso no dashboard
    comp = comp.rename(columns={
        'data':     'data_previsao',
        'predito':  'preco_previsto'
    })

    # 8) Filtra apenas os tickers desejados, se especificados
    if tickers:
        tickers_upper = [t.upper() for t in tickers]
        comp = comp[comp['acao'].isin(tickers_upper)]

    # 9) Persiste no banco, se solicitado
    if save_to_db:
        salvar_resultados_no_banco(comp, data_calculo)

    return model, comp

def executar_pipeline_multidia(
    max_dias: int = 10,
    data_calculo: date | None = None,
    save_to_db: bool = True,
    tickers: list[str] | None = None,
    progress_callback=None
) -> pd.DataFrame:
    """
    Executa um pipeline de regressão otimizado para prever múltiplos dias futuros.

    Args:
        max_dias: Número máximo de dias futuros para prever.
        data_calculo: Data base para o cálculo (se None, usa a data de hoje).
        save_to_db: Se True, persiste os resultados no banco de dados.
        tickers: Lista de ações para filtrar o resultado (ou None para todas).
        progress_callback: Função opcional para reportar o progresso (ex: para a UI).

    Returns:
        DataFrame com as previsões para cada dia até max_dias.
    """
    if data_calculo is None:
        data_calculo = date.today()

    # 1) Carregamento e preparação de dados (FEITO APENAS UMA VEZ)
    print("ETAPA 1: Carregando e preparando os dados (uma única vez)...")
    df_base = carregar_dados_do_banco()
    df_com_features = calcular_features_graham_estrito(df_base)
    print("✅ Dados preparados.")

    all_predictions = []

    # 2) Loop para treinar um modelo para cada horizonte de tempo (de 1 a max_dias)
    for n in range(1, max_dias + 1):
        if progress_callback:
            progress_callback(n, max_dias)

        print(f"\nETAPA 2: Treinando modelo para prever {n} dia(s) à frente...")

        # Adiciona a coluna 'preco_futuro_N_dias' para o horizonte 'n' atual
        df_horizonte = adicionar_preco_futuro(df_com_features, n)
        df_horizonte = df_horizonte.dropna(subset=['preco_futuro_N_dias']).copy()

        features = [
            'pl','pvp','dividend_yield','payout','margem_liquida','margem_bruta',
            'margem_ebit','margem_ebitda','ev_ebit','p_ebit',
            'p_ativo','p_cap_giro','p_ativo_circ_liq','vpa','lpa',
            'giro_ativos','roe','roic','roa','patrimonio_ativos',
            'passivos_ativos','variacao_12m'
        ]
        features = [f for f in features if f in df_horizonte.columns]

        X = df_horizonte[features].replace([np.inf, -np.inf], np.nan).dropna()
        y = df_horizonte.loc[X.index, 'preco_futuro_N_dias']
        dates = df_horizonte.loc[X.index, 'data_coleta']
        acoes = df_horizonte.loc[X.index, 'acao']

        # Define o conjunto de treino com base na data de cálculo
        cutoff = pd.to_datetime(data_calculo)
        mask_train = dates <= cutoff
        X_train, y_train = X[mask_train], y[mask_train]
        
        # Pega os dados mais recentes de cada ação para fazer a previsão
        ultimos_registros = X_train.groupby(acoes.loc[X_train.index]).tail(1)
        
        if ultimos_registros.empty:
            print(f"⚠️ Sem dados de treino para o horizonte de {n} dias na data {data_calculo}.")
            continue

        # Treina um modelo específico para este horizonte de dias
        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        # Gera previsões
        preds = model.predict(ultimos_registros)
        
        future_date = data_calculo + timedelta(days=n)

        comp = pd.DataFrame({
            'acao': acoes.loc[ultimos_registros.index].values,
            'data_previsao': [future_date] * len(ultimos_registros),
            'preco_previsto': preds,
            'dias_a_frente': n  # Adiciona a informação do horizonte
        })
        all_predictions.append(comp)

    if not all_predictions:
        print("❌ Nenhuma previsão pôde ser gerada.")
        return pd.DataFrame()

    # 3) Consolida e retorna os resultados
    final_comp = pd.concat(all_predictions, ignore_index=True)
    final_comp = final_comp.sort_values(['acao', 'dias_a_frente'])

    # Filtra tickers, se especificado
    if tickers:
        tickers_upper = [t.upper() for t in tickers]
        final_comp = final_comp[final_comp['acao'].isin(tickers_upper)]

    # Salva no banco, se solicitado
    if save_to_db:
        print("\nETAPA 3: Salvando resultados no banco...")
        salvar_resultados_no_banco(final_comp, data_calculo)

    return final_comp


if __name__ == "__main__":
    from datetime import datetime, date, timedelta

    # número padrão de dias
    try:
        n_dias = 10
    except ValueError:
        print("Valor inválido para n_dias. Encerrando...")
        exit()

    # data máxima disponível no banco
    data_maxima = obter_data_calculo_maxima()

    # menu
    print("\nEscolha uma opção:")
    print(f"1 - Prever {n_dias} dias no futuro a partir de HOJE e salvar no banco")
    print(f"2 - Prever {n_dias} dias no futuro a partir de uma data manual e salvar no banco")
    print(f"3 - Prever {n_dias} dias no futuro para um intervalo de datas e salvar no banco")
    print("4 - Prever N dias no futuro a partir de HOJE sem salvar no banco")
    print("5 - Prever N dias para uma AÇÃO específica (sem salvar no banco)")

    escolha = input("\nDigite 1, 2, 3, 4 ou 5: ").strip()

    if escolha == "1":
        data_calculo = date.today()
        if data_calculo > data_maxima:
            print(f"\n❌ ERRO: data_calculo não pode ser maior que {data_maxima}.")
            exit()
        print(f"\n✅ Iniciando previsão para {n_dias} dias a partir de {data_calculo} (salvando no banco)...\n")
        executar_pipeline_regressor(n_dias=n_dias, data_calculo=data_calculo)

    elif escolha == "2":
        data_input = input(f"Data cálculo (AAAA-MM-DD) até {data_maxima}: ").strip()
        try:
            data_calculo = datetime.strptime(data_input, "%Y-%m-%d").date()
            if data_calculo > data_maxima:
                print(f"\n❌ ERRO: data_calculo não pode ser maior que {data_maxima}.")
                exit()
        except ValueError:
            print("Formato inválido. Use AAAA-MM-DD.")
            exit()
        print(f"\n✅ Iniciando previsão para {n_dias} dias a partir de {data_calculo} (salvando no banco)...\n")
        executar_pipeline_regressor(n_dias=n_dias, data_calculo=data_calculo)

    elif escolha == "3":
        inicio = input(f"Data inicial (AAAA-MM-DD) até {data_maxima}: ").strip()
        fim    = input(f"Data final   (AAAA-MM-DD) até {data_maxima}: ").strip()
        try:
            data_inicio = datetime.strptime(inicio, "%Y-%m-%d").date()
            data_fim    = datetime.strptime(fim,    "%Y-%m-%d").date()
            if data_inicio > data_fim or data_fim > data_maxima:
                print("Intervalo inválido.")
                exit()
        except ValueError:
            print("Formato inválido. Use AAAA-MM-DD.")
            exit()
        print(f"\n✅ Iniciando previsões de {n_dias} dias de {data_inicio} até {data_fim} (salvando no banco)...\n")
        atual = data_inicio
        while atual <= data_fim:
            print(f"\n👉 Prevendo para {atual}...")
            executar_pipeline_regressor(n_dias=n_dias, data_calculo=atual)
            atual += timedelta(days=1)

    elif escolha == "4":
        dias = input("Quantos dias à frente? ").strip()
        try:
            n_dias_custom = int(dias)
        except ValueError:
            print("Número de dias inválido.")
            exit()
        print(f"\n✅ Prevendo {n_dias_custom} dias a partir de hoje (sem salvar)...\n")
        _, comp = executar_pipeline_regressor(n_dias=n_dias_custom, data_calculo=date.today(), save_to_db=False)
        print("\n📄 Resultados:")
        print(comp)

    elif escolha == "5":
        dias   = input("Quantos dias à frente? ").strip()
        ticker = input("Ticker da ação (ex: PETR4): ").strip().upper()
        try:
            n_dias_custom = int(dias)
        except ValueError:
            print("Número de dias inválido.")
            exit()
        print(f"\n✅ Prevendo {n_dias_custom} dias para {ticker} (sem salvar)...\n")
        _, comp = executar_pipeline_regressor(n_dias=n_dias_custom, data_calculo=date.today(), save_to_db=False)
        comp_filtrado = comp[comp['acao'] == ticker]
        if comp_filtrado.empty:
            print(f"\n⚠️ Nenhum resultado encontrado para {ticker}.")
        else:
            print("\n📄 Resultado da previsão para", ticker)
            print(comp_filtrado)

    else:
        print("\n❌ Opção inválida. Encerrando...")
        exit()
