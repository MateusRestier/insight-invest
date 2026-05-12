import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd, numpy as np
from datetime import datetime, timedelta, date
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from pandas.tseries.offsets import BDay
from src.core.db_connection import get_connection
from src.models.feature_engineering import (
    calcular_features_graham_estrito,
    adicionar_delta_features,
    adicionar_features_relativas,
    preparar_X,
    FEATURES_REGRESSOR,
)

# 1) Carrega o histórico
def carregar_dados_do_banco():
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql_query(
            "SELECT * FROM indicadores_fundamentalistas WHERE cotacao >= 1.0 ORDER BY acao, data_coleta;",
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
    """
    Calcula o preço alvo N dias úteis à frente (BDay), evitando inconsistências
    causadas por fins de semana/feriados que acontecem com dias calendário.
    """
    df = df.copy()
    df['data_futura_alvo'] = df['data_coleta'] + BDay(n_dias)

    def _por_acao(grp, acao_key):
        grp = grp.sort_values('data_coleta')
        grp['acao'] = acao_key
        left = grp[['data_futura_alvo']].copy().sort_values('data_futura_alvo')
        right = grp[['data_coleta', 'cotacao']].copy().sort_values('data_coleta')

        # merge_asof exige dtypes idênticos nas chaves de data
        left['data_futura_alvo'] = pd.to_datetime(left['data_futura_alvo']).astype('datetime64[ns]')
        right['data_coleta'] = pd.to_datetime(right['data_coleta']).astype('datetime64[ns]')

        merged = pd.merge_asof(
            left=left, right=right,
            left_on='data_futura_alvo', right_on='data_coleta',
            direction='forward'
        )
        # Descarta matches muito distantes da data-alvo.
        # direction='forward' pode atravessar lacunas longas de dados (ex: 7 meses sem coleta),
        # atribuindo o preco de muito no futuro como se fosse o alvo de 10 dias.
        # Tolerância de 30 dias cobre fins de semana + feriados prolongados sem silenciar dados legítimos.
        _tolerance = pd.Timedelta(days=30)
        _too_far = (merged['data_coleta'] - merged['data_futura_alvo']) > _tolerance
        cotacao_filtrada = merged['cotacao'].where(~_too_far, other=np.nan)
        grp = grp.assign(preco_futuro_N_dias=cotacao_filtrada.values)
        return grp

    df = df.groupby('acao', group_keys=False, dropna=False).apply(
        lambda grp: _por_acao(grp, grp.name)
    )
    df = df.drop(columns=['data_futura_alvo'])

    # Em algumas versões/cenários de pandas, 'acao' pode virar nível de índice
    if 'acao' not in df.columns:
        if isinstance(df.index, pd.MultiIndex) and 'acao' in df.index.names:
            df = df.reset_index(level='acao')
        elif df.index.name == 'acao':
            df = df.reset_index()

    return df

# 3) Prepara X, y, dates
def preparar_dados_regressao(df, n_dias):
    # Fallback caso 'acao' seja movida para índice durante transformações
    acao_fallback = None
    if 'acao' in df.columns:
        acao_fallback = df['acao'].copy()
    elif isinstance(df.index, pd.MultiIndex) and 'acao' in df.index.names:
        acao_fallback = pd.Series(
            df.index.get_level_values('acao'),
            index=df.index,
            name='acao'
        )
    elif df.index.name == 'acao':
        acao_fallback = pd.Series(df.index, index=df.index, name='acao')

    # Pipeline de feature engineering completo
    df = calcular_features_graham_estrito(df)
    df = adicionar_delta_features(df, janela_dias=7)
    df = adicionar_features_relativas(df)
    df = adicionar_preco_futuro(df, n_dias)
    df = df.dropna(subset=['preco_futuro_N_dias']).copy()

    if 'acao' not in df.columns:
        if isinstance(df.index, pd.MultiIndex) and 'acao' in df.index.names:
            df = df.reset_index(level='acao')
        elif df.index.name == 'acao':
            df = df.reset_index()
        elif acao_fallback is not None:
            df['acao'] = acao_fallback.reindex(df.index).values
        else:
            raise KeyError("Coluna 'acao' ausente após preparação dos dados de regressão.")

    # Usa a lista centralizada de features; mantém apenas as que existem no df
    features = [f for f in FEATURES_REGRESSOR if f in df.columns]

    X = preparar_X(df, features)
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


# 5a) Pré-carregamento para backfill (evita recarregar dados a cada iteração)
def preparar_dados_cache(n_dias: int = 10) -> tuple:
    """
    Carrega e processa os dados uma única vez para uso em backfills.
    Retorna (X, y, dates, acoes, ultima_real_date) pronto para passar a
    executar_pipeline_regressor via _dados_cache.
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM indicadores_fundamentalistas WHERE cotacao >= 1.0 ORDER BY acao, data_coleta;",
        conn
    )
    conn.close()
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])
    ultima_real_date = df['data_coleta'].max().date()
    X, y, dates, acoes = preparar_dados_regressao(df, n_dias)
    return X, y, dates, acoes, ultima_real_date


# 5b) Pipeline completo
def executar_pipeline_regressor(
    n_dias: int = 10,
    data_calculo: date | None = None,
    save_to_db: bool = True,
    tickers: list[str] | None = None,
    sem_vazamento_temporal: bool = False,
    _dados_cache: tuple | None = None,
) -> tuple[RandomForestRegressor, pd.DataFrame]:
    """
    Executa o pipeline de regressão para previsão de preços.
    Args:
        n_dias: número de dias futuros para prever.
        data_calculo: data base para cálculo (se None, usa hoje).
        save_to_db: se True, persiste em resultados_precos.
        tickers: lista de ações para filtrar o resultado (ou None para todas).
        sem_vazamento_temporal: quando True, treina apenas com linhas cujo alvo
            (preço em n_dias à frente) já seria conhecido na data_calculo.
        _dados_cache: tupla (X, y, dates, acoes, ultima_real_date) pré-computada
            para evitar recarregar e reprocessar dados em chamadas repetidas (backfill).
    Returns:
        model: RandomForestRegressor treinado.
        comp: DataFrame com colunas ['acao','data_previsao','real','preco_previsto','erro_pct'].
    """
    if data_calculo is None:
        data_calculo = date.today()

    if _dados_cache is not None:
        X, y, dates, acoes, ultima_real_date = _dados_cache
    else:
        # 1) Carrega histórico de indicadores
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM indicadores_fundamentalistas WHERE cotacao >= 1.0", conn)
        conn.close()
        df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        ultima_real_date = df['data_coleta'].max().date()
        # 2) Prepara X, y, datas e tickers
        X, y, dates, acoes = preparar_dados_regressao(df, n_dias)

    # 3) Define máscaras de treino/teste com base em data_calculo
    cutoff = pd.to_datetime(data_calculo)
    if data_calculo > ultima_real_date:
        print(f"⚠️ data_calculo ({data_calculo}) > última data no banco ({ultima_real_date}); ajustando treino.")
        ultima_ts = pd.to_datetime(ultima_real_date)
        if sem_vazamento_temporal:
            limite_treino = ultima_ts - pd.Timedelta(days=n_dias)
            mask_train = dates <= limite_treino
        else:
            mask_train = dates <= ultima_ts
        mask_test  = pd.Series(False, index=dates.index)
    else:
        if sem_vazamento_temporal:
            limite_treino = cutoff - pd.Timedelta(days=n_dias)
            mask_train = dates <= limite_treino
        else:
            mask_train = dates < cutoff
        mask_test  = dates == cutoff

    X_train, y_train = X[mask_train], y[mask_train]
    X_test,  y_test  = X[mask_test],  y[mask_test]
    acoes_test       = acoes[mask_test]

    # 4) Treina o modelo com busca de hiperparâmetros
    n_samples = len(X_train)
    # Com poucos dados usa 3 splits; com mais usa 5
    n_splits = 3 if n_samples < 500 else 5
    tscv = TimeSeriesSplit(n_splits=n_splits)

    param_dist = {
        'n_estimators': [100, 200, 300],
        'max_depth': [5, 10, 15, None],
        'min_samples_leaf': [2, 5, 10],
        'max_features': ['sqrt', 'log2', 0.5],
    }
    search = RandomizedSearchCV(
        RandomForestRegressor(random_state=42),
        param_distributions=param_dist,
        n_iter=5,
        cv=tscv,
        scoring='neg_mean_absolute_error',
        n_jobs=-1,
        random_state=42,
        verbose=0,
    )
    search.fit(X_train, y_train)
    model = search.best_estimator_
    print(f"[regressor] Melhores parametros: {search.best_params_}")
    print(f"[regressor] Melhor MAE (CV): {-search.best_score_:.4f}")

    # 5) Gera previsões (data alvo em dias úteis, consistente com adicionar_preco_futuro)
    future_date = (pd.Timestamp(data_calculo) + BDay(n_dias)).date()
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
    df_com_features = adicionar_delta_features(df_com_features, janela_dias=7)
    df_com_features = adicionar_features_relativas(df_com_features)
    print("✅ Dados preparados.")

    all_predictions = []

    # 2) Loop para treinar um modelo para cada horizonte de tempo (de 1 a max_dias)
    for n in range(1, max_dias + 1):
        if progress_callback:
            progress_callback(n, max_dias)

        print(f"\nETAPA 2: Treinando modelo para prever {n} dia(s) úteis à frente...")

        # Adiciona a coluna 'preco_futuro_N_dias' para o horizonte 'n' atual (BDay)
        df_horizonte = adicionar_preco_futuro(df_com_features, n)
        df_horizonte = df_horizonte.dropna(subset=['preco_futuro_N_dias']).copy()

        features = [f for f in FEATURES_REGRESSOR if f in df_horizonte.columns]

        X = preparar_X(df_horizonte, features)
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

        # Treina com RandomizedSearchCV
        n_splits = 2 if len(X_train) < 500 else 5
        tscv = TimeSeriesSplit(n_splits=n_splits)
        param_dist = {
            'n_estimators': [100, 200, 300],
            'max_depth': [5, 10, 15, None],
            'min_samples_leaf': [2, 5, 10],
            'max_features': ['sqrt', 'log2', 0.5],
        }
        search = RandomizedSearchCV(
            RandomForestRegressor(random_state=42),
            param_distributions=param_dist,
            n_iter=5, cv=tscv,
            scoring='neg_mean_absolute_error',
            n_jobs=-1, random_state=42, verbose=0,
        )
        search.fit(X_train, y_train)
        model = search.best_estimator_

        # Gera previsões
        preds = model.predict(ultimos_registros)

        future_date = (pd.Timestamp(data_calculo) + BDay(n)).date()

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
