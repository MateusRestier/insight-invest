import pandas as pd #ADICIONAR MAIS COLUNAS NA CONSULTA
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import psycopg2

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

def carregar_dados_do_banco():
    """Carrega os dados da tabela indicadores_fundamentalistas do banco de dados."""
    conn = None
    try:
        conn = get_connection()
        query = "SELECT acao, data_coleta, cotacao, lpa, vpa FROM indicadores_fundamentalistas ORDER BY acao, data_coleta;" # Ordenar aqui
        # Carregando apenas colunas necessárias para esta etapa, mais as de Graham.
        # Se outras colunas forem necessárias para features do modelo, adicione-as.
        df = pd.read_sql_query(query, conn)
        print(f"Dados carregados do banco com sucesso! Shape: {df.shape}")
        return df
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao carregar dados do banco: {error}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def calcular_features_graham_estrito(df_input):
    """Calcula o VI de Graham e a feature Preco_Sobre_Graham de forma estrita."""
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
         # Certificar que 'data_coleta' é datetime para ordenação correta se não for índice ainda
        if 'data_coleta' in df.columns:
             df['data_coleta'] = pd.to_datetime(df['data_coleta'])
        # Ordenação crucial para o shift funcionar corretamente por grupo
        df = df.sort_values(by=['acao', 'data_coleta'])


    print(f"Calculando rótulos para N={n_dias} dias, q_inf={q_inferior}, q_sup={q_superior}")

    # Calcular o preço futuro N dias à frente para cada ação
    # O groupby().shift() olha para N linhas anteriores/posteriores DENTRO de cada grupo 'acao'.
    # Um shift negativo olha para frente.
    df['preco_futuro_N_dias'] = df.groupby('acao')['cotacao'].shift(-n_dias)

    # Calcular o retorno futuro
    # Garantir que não haja divisão por zero se a cotação for 0 (improvável, mas seguro)
    df['retorno_futuro_N_dias'] = np.where(
        df['cotacao'] > 0,
        (df['preco_futuro_N_dias'] - df['cotacao']) / df['cotacao'],
        np.nan
    )

    # Inicializar a coluna de rótulos
    df['rotulo_desempenho_futuro'] = np.nan

    # Calcular quantis e atribuir rótulos para cada dia de coleta
    # Iterar sobre as datas onde o retorno futuro é calculável
    datas_com_retorno_valido = df.dropna(subset=['retorno_futuro_N_dias'])['data_coleta'].unique()
    
    print(f"Número de datas únicas com retorno futuro válido: {len(datas_com_retorno_valido)}")
    if not datas_com_retorno_valido.any():
        print("Nenhuma data com retorno futuro válido encontrada. Verifique o tamanho do dataset e N.")
        return df

    for data_atual in datas_com_retorno_valido:
        # Filtra os dados para o dia atual que possuem retorno futuro calculado
        dia_df = df[(df['data_coleta'] == data_atual) & (df['retorno_futuro_N_dias'].notna())].copy() # Adicionado .copy()
        
        if dia_df.empty:
            continue

        # Calcular os quantis dos retornos para este dia específico
        quantil_inf = dia_df['retorno_futuro_N_dias'].quantile(q_inferior)
        quantil_sup = dia_df['retorno_futuro_N_dias'].quantile(q_superior)

        # Atribuir rótulos com base nos quantis
        # Usar .loc para atribuição no DataFrame original 'df' filtrado pelo índice de 'dia_df'
        # df.loc[dia_df.index, 'rotulo_desempenho_futuro'] = np.select( (...) ) <- pode ser complexo com np.select
        
        # Abordagem mais simples com .loc e condições:
        indices_dia = dia_df.index
        
        # Rótulo 0 para quem está abaixo ou igual ao quantil inferior
        df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] <= quantil_inf], 'rotulo_desempenho_futuro'] = 0
        
        # Rótulo 1 para quem está acima ou igual ao quantil superior
        df.loc[indices_dia[dia_df['retorno_futuro_N_dias'] >= quantil_sup], 'rotulo_desempenho_futuro'] = 1
        
        # Se quantil_inf == quantil_sup (poucos dados distintos no dia), todos podem receber 0 ou 1.
        # A lógica acima prioriza 0 se for igual ao inferior, e 1 se for igual ao superior.
        # Se uma ação estiver exatamente no limite e cair em ambas as condições, a última atribuição (para 1) prevalecerá.
        # Para evitar isso se q_inf e q_sup forem muito próximos ou iguais:
        if quantil_inf == quantil_sup:
            # Em caso de empate nos quantis (pouca variabilidade no dia), podemos decidir não rotular
            # ou rotular todos de uma forma específica. Por simplicidade, a lógica acima os rotularia como 1.
            # Para uma distinção clara, se os quantis são iguais, talvez esses rótulos não sejam ideais para o dia.
            # No entanto, na prática, é raro se houver dados suficientes.
            pass


    print("\nExemplo de dados com rótulos de desempenho futuro (primeiras ocorrências com rótulo):")
    print(df[df['rotulo_desempenho_futuro'].notna()][['acao', 'data_coleta', 'cotacao', 'preco_futuro_N_dias', 'retorno_futuro_N_dias', 'rotulo_desempenho_futuro']].head(10))
    
    print("\nContagem de rótulos:")
    print(df['rotulo_desempenho_futuro'].value_counts(dropna=False))
    
    return df

def analisar_e_mostrar_resultados_graham(df_com_graham):
    """Realiza a análise da feature de Graham e imprime os resultados."""
    if df_com_graham.empty or 'preco_sobre_graham' not in df_com_graham.columns:
        print("DataFrame para Graham vazio ou coluna 'preco_sobre_graham' ausente.")
        return

    print("\nEstatísticas Descritivas da feature 'preco_sobre_graham' (cálculo estrito):")
    print(df_com_graham['preco_sobre_graham'].describe())

    preco_sobre_graham_plot = df_com_graham['preco_sobre_graham'].replace([np.inf, -np.inf], np.nan).dropna()

    if not preco_sobre_graham_plot.empty:
        plt.figure(figsize=(12, 7))
        sns.histplot(preco_sobre_graham_plot, kde=True, bins=50)
        plt.title('Distribuição da Feature Preco_Sobre_Graham (P/VG - Cálculo Estrito)', fontsize=16)
        # ... (resto do código de plotagem como antes) ...
        plot_filename = "preco_sobre_graham_dist_db_estrito.png"
        try:
            plt.savefig(plot_filename)
            print(f"\nHistograma da distribuição de Graham salvo em: {plot_filename}")
        except Exception as e:
            print(f"Erro ao salvar o histograma de Graham: {e}")
        plt.close() # Fechar a figura para liberar memória
    else:
        print("\nNão foi possível gerar o histograma de Graham.")


def main():
    """Função principal para executar o pipeline."""
    print("Iniciando o processo...")
    
    df_original = carregar_dados_do_banco()

    if df_original.empty:
        print("Não foi possível carregar dados do banco. Encerrando.")
        return

    if 'data_coleta' in df_original.columns:
        df_original['data_coleta'] = pd.to_datetime(df_original['data_coleta'], errors='coerce')
    else:
        print("Aviso: Coluna 'data_coleta' não encontrada.")
        # Adicionar uma coluna 'data_coleta' vazia pode ser necessário se o resto do código depender dela
        # df_original['data_coleta'] = pd.NaT 

    # Calcular features de Graham
    df_com_graham = calcular_features_graham_estrito(df_original)
    analisar_e_mostrar_resultados_graham(df_com_graham) # Mostra análise de Graham

    # Calcular rótulos de desempenho futuro
    # Vamos usar o df_com_graham, pois ele já tem as colunas de Graham que podem ser features X no futuro.
    # Se o df_original fosse usado, teríamos que juntar depois.
    df_com_rotulos = calcular_rotulos_desempenho_futuro(df_com_graham, n_dias=10, q_inferior=0.25, q_superior=0.75)

    print("\n DataFrame final com rótulos (últimas linhas para inspeção):")
    print(df_com_rotulos[['acao', 'data_coleta', 'cotacao', 'preco_sobre_graham', 'retorno_futuro_N_dias', 'rotulo_desempenho_futuro']].tail(10))
    
    # O próximo passo seria preparar X e y a partir de df_com_rotulos
    # e alimentar o classificador.
    # Ex: df_para_modelo = df_com_rotulos.dropna(subset=['rotulo_desempenho_futuro'])
    #      y = df_para_modelo['rotulo_desempenho_futuro']
    #      X = df_para_modelo[['preco_sobre_graham', ... outras features ... ]]
    #      Tratar NaNs em X, etc.

    print("\nProcesso concluído.")

if __name__ == "__main__":
    # os.environ["DB_HOST"] = "localhost"
    # os.environ["DB_NAME"] = "stocks"
    # os.environ["DB_USER"] = "user"
    # os.environ["DB_PASS"] = "password"
    # os.environ["DB_PORT"] = "5432"
    
    main()