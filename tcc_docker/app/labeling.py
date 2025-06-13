import pandas as pd
import numpy as np

def calcular_rotulos_desempenho_futuro(df_input, n_dias=10, q_inferior=0.25, q_superior=0.75):
    """
    Calcula os rótulos de desempenho futuro relativo de forma robusta, usando datas.
    Esta versão funciona tanto para dados diários quanto para dados agregados (semanais, etc.).
    
    1: Top X% (definido por q_superior)
    0: Bottom Y% (definido por q_inferior)
    NaN: Meio (será descartado)
    """
    df = df_input.copy()
    
    if 'data_coleta' not in df.columns or 'acao' not in df.columns or 'cotacao' not in df.columns:
        print("Erro: DataFrame de entrada precisa das colunas 'data_coleta', 'acao' e 'cotacao'.")
        return df

    # Garantir que a data_coleta seja do tipo datetime e ordenar
    df['data_coleta'] = pd.to_datetime(df['data_coleta'])
    df = df.sort_values(by='data_coleta')

    # Criar uma coluna com a data futura que queremos encontrar
    df['data_futura_alvo'] = df['data_coleta'] + pd.to_timedelta(n_dias, unit='d')

    # Usamos pd.merge_asof, a ferramenta correta para "procurar o valor mais próximo no tempo"
    # Para cada linha do dataframe original ('left'), ele procurará no mesmo dataframe ('right')
    # a primeira linha que tenha a mesma 'acao' e cuja 'data_coleta' seja igual ou posterior
    # à 'data_futura_alvo'.
    df_futuro = pd.merge_asof(
        left=df[['acao', 'data_futura_alvo']],
        right=df[['acao', 'data_coleta', 'cotacao']],
        left_on='data_futura_alvo',
        right_on='data_coleta',
        by='acao',
        direction='forward'  # 'forward' significa pegar o próximo valor disponível no futuro
    )

    # Renomear a coluna de cotação futura encontrada
    df_futuro.rename(columns={'cotacao': 'preco_futuro_N_dias'}, inplace=True)

    # Juntar os preços futuros de volta ao nosso dataframe original
    # Usamos o índice para garantir o alinhamento correto
    df['preco_futuro_N_dias'] = df_futuro['preco_futuro_N_dias'].values

    # Calcular o retorno futuro (lógica original mantida)
    df['retorno_futuro_N_dias'] = np.where(
        df['cotacao'] > 0,
        (df['preco_futuro_N_dias'] - df['cotacao']) / df['cotacao'],
        np.nan
    )

    # A lógica de cálculo dos quantis para cada dia permanece a mesma, pois é robusta
    df['rotulo_desempenho_futuro'] = np.nan
    datas_com_retorno_valido = df.dropna(subset=['retorno_futuro_N_dias'])['data_coleta'].unique()

    for data_atual in datas_com_retorno_valido:
        # Filtra o dia, garantindo que o retorno seja válido
        dia_df = df[(df['data_coleta'] == data_atual) & (df['retorno_futuro_N_dias'].notna())].copy()

        if dia_df.empty:
            continue

        # Verifica se há dados suficientes para calcular quantis
        if len(dia_df['retorno_futuro_N_dias'].dropna()) < 4: # Precisa de pelo menos 4 pontos para quantis
            continue

        quantil_inf = dia_df['retorno_futuro_N_dias'].quantile(q_inferior)
        quantil_sup = dia_df['retorno_futuro_N_dias'].quantile(q_superior)

        indices_dia = dia_df.index
        
        # Atribui rótulos apenas se os quantis forem diferentes para evitar classificar tudo igual
        if quantil_inf != quantil_sup:
            df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] <= quantil_inf], 'rotulo_desempenho_futuro'] = 0
            df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] >= quantil_sup], 'rotulo_desempenho_futuro'] = 1

    # Remove colunas auxiliares
    df.drop(columns=['data_futura_alvo', 'preco_futuro_N_dias'], inplace=True, errors='ignore')

    return df