import pandas as pd
import numpy as np

def calcular_rotulos_desempenho_futuro(df_input, n_dias=10, q_inferior=0.25, q_superior=0.75):
    """
    Calcula os rótulos de desempenho futuro relativo:
    1: Top X% (definido por q_superior)
    0: Bottom Y% (definido por q_inferior)
    NaN: Meio (será descartado)
    
    Parâmetros:
    - df_input: DataFrame com as ações e dados necessários (cotação, retorno, etc.)
    - n_dias: Número de dias no futuro para previsão
    - q_inferior: Percentual inferior para rótulo 0
    - q_superior: Percentual superior para rótulo 1
    
    Retorna:
    - DataFrame com a coluna 'rotulo_desempenho_futuro' preenchida.
    """
    df = df_input.copy()

    if not isinstance(df.index, pd.MultiIndex) and not df.empty:
        if 'data_coleta' in df.columns:
            df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        else:
            print("Aviso: Coluna 'data_coleta' não encontrada.")
            return df
        
        df = df.sort_values(by=['acao', 'data_coleta'])

    # Calcular o preço futuro N dias à frente para cada ação
    df['preco_futuro_N_dias'] = df.groupby('acao')['cotacao'].shift(-n_dias)

    # Calcular o retorno futuro
    df['retorno_futuro_N_dias'] = np.where(
        df['cotacao'] > 0,
        (df['preco_futuro_N_dias'] - df['cotacao']) / df['cotacao'],
        np.nan
    )

    # Inicializar a coluna de rótulos
    df['rotulo_desempenho_futuro'] = np.nan

    # Calcular quantis e atribuir rótulos para cada dia de coleta
    datas_com_retorno_valido = df.dropna(subset=['retorno_futuro_N_dias'])['data_coleta'].unique()

    for data_atual in datas_com_retorno_valido:
        dia_df = df[(df['data_coleta'] == data_atual) & (df['retorno_futuro_N_dias'].notna())].copy()

        if dia_df.empty:
            continue

        quantil_inf = dia_df['retorno_futuro_N_dias'].quantile(q_inferior)
        quantil_sup = dia_df['retorno_futuro_N_dias'].quantile(q_superior)

        indices_dia = dia_df.index
        
        df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] <= quantil_inf], 'rotulo_desempenho_futuro'] = 0
        df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] >= quantil_sup], 'rotulo_desempenho_futuro'] = 1

        # Se quantil_inf == quantil_sup, todos podem receber 0 ou 1, mas isso será raro com dados suficientes
        if quantil_inf == quantil_sup:
            pass  # Pode-se implementar estratégia para lidar com isso
    return df