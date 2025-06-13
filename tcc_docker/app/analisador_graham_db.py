import pandas as pd, numpy as np, matplotlib.pyplot as plt, seaborn as sns, psycopg2, os
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
        # exit()

def carregar_dados_do_banco():
    """Carrega os dados da tabela indicadores_fundamentalistas do banco de dados."""
    conn = None
    try:
        conn = get_connection()
        query = "SELECT acao, pl, pvp, data_coleta, cotacao, lpa, vpa FROM indicadores_fundamentalistas ORDER BY acao, data_coleta;" # Ordenar aqui
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