import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import psycopg2 # Adicionado para get_connection

# Tenta importar do local padrão do seu projeto TCC
try:
    from app.db_connection import get_connection
except ImportError:
    # Fallback se o script não estiver sendo executado de um nível acima da pasta 'app'
    # ou se 'app' não for um pacote reconhecido no PYTHONPATH atual.
    # Isso pode precisar de ajuste dependendo de onde você executa o script.
    try:
        from db_connection import get_connection
        print("Importou 'get_connection' do diretório atual.")
    except ImportError as e:
        print(f"Erro ao importar 'get_connection': {e}")
        print("Certifique-se de que db_connection.py está acessível e as variáveis de ambiente do DB estão configuradas.")
        # Você pode querer sair do script aqui se a conexão não for possível
        # exit()


def carregar_dados_do_banco():
    """Carrega os dados da tabela indicadores_fundamentalistas do banco de dados."""
    conn = None
    try:
        conn = get_connection()
        query = "SELECT * FROM indicadores_fundamentalistas;"
        df = pd.read_sql_query(query, conn)
        print(f"Dados carregados do banco com sucesso! Shape: {df.shape}")
        return df
    except (Exception, psycopg2.Error) as error:
        print(f"Erro ao carregar dados do banco: {error}")
        return pd.DataFrame() # Retorna DataFrame vazio em caso de erro
    finally:
        if conn:
            conn.close()

def calcular_features_graham(df_input):
    """Calcula o VI de Graham e a feature Preco_Sobre_Graham."""
    df = df_input.copy() # Evitar SettingWithCopyWarning
    
    # Certificar que colunas LPA, VPA e cotacao são numéricas e lidar com erros
    # O read_sql_query geralmente já lida com tipos, mas uma verificação extra é boa.
    cols_to_numeric = ['lpa', 'vpa', 'cotacao']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            print(f"Aviso: Coluna '{col}' não encontrada no DataFrame.")
            # Adicionar a coluna com NaNs para evitar erros posteriores se ela for essencial
            df[col] = np.nan 
            
    # 1. Calcular o Valor Intrínseco de Graham (VI_Graham)
    produto_lpa_vpa = 22.5 * df['lpa'] * df['vpa']
    df['vi_graham'] = np.where(produto_lpa_vpa > 0, np.sqrt(produto_lpa_vpa), np.nan)

    # 2. Calcular a feature Preco_Sobre_Graham (P/VG)
    df['preco_sobre_graham'] = np.where(
        (df['vi_graham'].notna()) & (df['vi_graham'] != 0),
        df['cotacao'] / df['vi_graham'],
        np.nan
    )
    return df

def analisar_e_mostrar_resultados(df_com_graham):
    """Realiza a análise da feature de Graham e imprime os resultados."""
    if df_com_graham.empty or 'preco_sobre_graham' not in df_com_graham.columns:
        print("DataFrame vazio ou coluna 'preco_sobre_graham' ausente. Não é possível analisar.")
        return

    print("\nDataFrame com as novas colunas 'vi_graham' e 'preco_sobre_graham' (primeiras 5 linhas):")
    print(df_com_graham[['acao', 'data_coleta', 'lpa', 'vpa', 'cotacao', 'vi_graham', 'preco_sobre_graham']].head())

    print("\nEstatísticas Descritivas da feature 'preco_sobre_graham':")
    print(df_com_graham['preco_sobre_graham'].describe())

    preco_sobre_graham_plot = df_com_graham['preco_sobre_graham'].replace([np.inf, -np.inf], np.nan).dropna()

    if not preco_sobre_graham_plot.empty:
        plt.figure(figsize=(12, 7)) # Aumentei um pouco o tamanho
        sns.histplot(preco_sobre_graham_plot, kde=True, bins=50)
        plt.title('Distribuição da Feature Preco_Sobre_Graham (P/VG)', fontsize=16)
        plt.xlabel('Preco_Sobre_Graham', fontsize=14)
        plt.ylabel('Frequência', fontsize=14)
        plt.grid(axis='y', linestyle='--', alpha=0.7) # Grade horizontal
        plt.tight_layout() # Ajustar layout
        
        # Salvar o gráfico em um arquivo temporário (ajuste o caminho conforme necessário)
        plot_filename = "preco_sobre_graham_dist_db.png" # Nome do arquivo local
        try:
            plt.savefig(plot_filename)
            print(f"\nHistograma da distribuição salvo em: {plot_filename}")
        except Exception as e:
            print(f"Erro ao salvar o histograma: {e}")
        plt.show() # Tenta exibir, pode não funcionar em todos os ambientes de script puro
        plt.close()

        df_valid_psg = df_com_graham.dropna(subset=['preco_sobre_graham'])
        df_valid_psg = df_valid_psg[~df_valid_psg['preco_sobre_graham'].isin([np.inf, -np.inf])]
        
        if not df_valid_psg.empty:
            print("\nTop 10 ações com menor Preco_Sobre_Graham (potencialmente subavaliadas):")
            # Para obter os valores mais recentes e únicos por ação:
            df_recent_lowest = df_valid_psg.sort_values(['acao', 'data_coleta'], ascending=[True, False]) \
                                          .drop_duplicates('acao', keep='first') \
                                          .sort_values('preco_sobre_graham')
            print(df_recent_lowest.head(10)[['acao', 'data_coleta', 'preco_sobre_graham', 'cotacao', 'vi_graham', 'lpa', 'vpa']])

            print("\nTop 10 ações com maior Preco_Sobre_Graham (potencialmente sobreavaliadas):")
            df_recent_highest = df_valid_psg.sort_values(['acao', 'data_coleta'], ascending=[True, False]) \
                                           .drop_duplicates('acao', keep='first') \
                                           .sort_values('preco_sobre_graham', ascending=False)
            print(df_recent_highest.head(10)[['acao', 'data_coleta', 'preco_sobre_graham', 'cotacao', 'vi_graham', 'lpa', 'vpa']])
        else:
            print("Não há dados válidos de 'preco_sobre_graham' para mostrar os top/bottom.")
            
    else:
        print("\nNão foi possível gerar o histograma ou mostrar exemplos pois a coluna 'preco_sobre_graham' não contém dados válidos após tratamento.")

def main():
    """Função principal para executar o pipeline."""
    print("Iniciando o processo de cálculo da feature de Graham a partir do banco de dados...")
    
    # Carregar os dados do banco
    df_original = carregar_dados_do_banco()

    if df_original.empty:
        print("Não foi possível carregar dados do banco. Encerrando.")
        return

    # Converter 'data_coleta' para datetime se não estiver no formato correto
    if 'data_coleta' in df_original.columns:
        df_original['data_coleta'] = pd.to_datetime(df_original['data_coleta'], errors='coerce')
    else:
        print("Aviso: Coluna 'data_coleta' não encontrada.")

    # Calcular as features de Graham
    df_com_graham = calcular_features_graham(df_original)

    # Analisar e mostrar os resultados
    analisar_e_mostrar_resultados(df_com_graham)

    # Salvar o DataFrame modificado para você poder usar depois, se quiser (opcional)
    # output_csv_filename = "indicadores_com_graham_do_banco.csv"
    # try:
    #     df_com_graham.to_csv(output_csv_filename, index=False)
    #     print(f"\nDataFrame com a feature de Graham salvo em: {output_csv_filename}")
    # except Exception as e:
    #     print(f"Erro ao salvar o CSV: {e}")

    print("\nProcesso concluído.")

if __name__ == "__main__":
    # Configurar variáveis de ambiente para teste local, se necessário.
    # No Docker, estas seriam fornecidas pelo docker-compose.yml ou Dockerfile.
    # Exemplo (DESCOMENTE E AJUSTE SE FOR RODAR LOCALMENTE FORA DO DOCKER E NÃO TIVER AS VARS GLOBAIS):
    # os.environ["DB_HOST"] = "localhost"
    # os.environ["DB_NAME"] = "stocks"
    # os.environ["DB_USER"] = "user"
    # os.environ["DB_PASS"] = "password"
    # os.environ["DB_PORT"] = "5432"
    
    main()