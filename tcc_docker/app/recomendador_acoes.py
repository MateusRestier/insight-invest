import os
import pandas as pd
import numpy as np
import joblib
from scraper_indicadores import coletar_indicadores

# Lista de features EXATAMENTE como o modelo foi treinado
FEATURES_ESPERADAS_PELO_MODELO = [
    'pl', 'psr', 'pvp', 'dividend_yield', 'payout', 'margem_liquida', 'margem_bruta',
    'margem_ebit', 'margem_ebitda', 'ev_ebitda', 'ev_ebit', 'p_ebitda', 'p_ebit',
    'p_ativo', 'p_cap_giro', 'p_ativo_circ_liq', 'vpa', 'lpa',
    'giro_ativos', 'roe', 'roic', 'roa', 'div_liq_patrimonio', 'div_liq_ebitda',
    'div_liq_ebit', 'div_bruta_patrimonio', 'patrimonio_ativos', 'passivos_ativos',
    'liquidez_corrente', 'variacao_12m',
    'preco_sobre_graham'
]

FEATURES_CHAVE_PARA_EXIBIR_E_JUSTIFICAR = [
    'pl', 'pvp', 'dividend_yield', 'roe', 'preco_sobre_graham',
    'variacao_12m', 'p_ebit', 'margem_liquida'
]

def calcular_preco_sobre_graham_para_recomendacao(dados_acao_dict):
    dados_copy = dados_acao_dict.copy()
    try:
        lpa = pd.to_numeric(dados_copy.get('lpa'), errors='coerce')
        vpa = pd.to_numeric(dados_copy.get('vpa'), errors='coerce')
        cotacao = pd.to_numeric(dados_copy.get('cotacao'), errors='coerce')
        vi_graham = np.nan
        preco_sobre_graham = np.nan
        if pd.notna(lpa) and pd.notna(vpa) and lpa > 0 and vpa > 0:
            produto_lpa_vpa = 22.5 * lpa * vpa
            vi_graham = np.sqrt(produto_lpa_vpa)
        if pd.notna(vi_graham) and vi_graham != 0 and pd.notna(cotacao):
            preco_sobre_graham = cotacao / vi_graham
        dados_copy['preco_sobre_graham'] = preco_sobre_graham
    except Exception as e:
        # Silencioso aqui, pois o erro já foi impresso no scraper se ocorreu lá
        dados_copy['preco_sobre_graham'] = np.nan
    return dados_copy

def carregar_artefatos_modelo():
    base_path = os.path.dirname(os.path.abspath(__file__))
    modelo_path = os.path.join(base_path, "modelo", "modelo_classificador_desempenho.pkl")
    imputer_path = os.path.join(base_path, "modelo", "imputer.pkl")
    if not os.path.exists(modelo_path):
        raise FileNotFoundError(f"Modelo não encontrado em {modelo_path}. Execute o classificador.py primeiro.")
    if not os.path.exists(imputer_path):
        raise FileNotFoundError(f"Imputer não encontrado em {imputer_path}. Execute o classificador.py para gerá-lo e salvá-lo.")
    modelo = joblib.load(modelo_path)
    imputer = joblib.load(imputer_path)
    print("Modelo e Imputer carregados com sucesso.")
    return modelo, imputer

def gerar_justificativas(dados_acao_df, predicao_texto_modelo): # Alterado para receber o texto da predição
    justificativas_positivas = []
    justificativas_negativas = []

    try:
        def get_numeric_feature(df, col_name):
            return pd.to_numeric(df.get(col_name, np.nan).iloc[0], errors='coerce')

        pl = get_numeric_feature(dados_acao_df, 'pl')
        pvp = get_numeric_feature(dados_acao_df, 'pvp')
        dy = get_numeric_feature(dados_acao_df, 'dividend_yield')
        roe = get_numeric_feature(dados_acao_df, 'roe')
        psg = get_numeric_feature(dados_acao_df, 'preco_sobre_graham')
        var12m = get_numeric_feature(dados_acao_df, 'variacao_12m')
        margem_liq = get_numeric_feature(dados_acao_df, 'margem_liquida')
        p_ebit = get_numeric_feature(dados_acao_df,'p_ebit')

        if pd.notna(pl):
            if 0 < pl < 10: justificativas_positivas.append(f"P/L baixo ({pl:.2f}), pode indicar subavaliação.")
            elif pl >= 10 and pl < 20: justificativas_positivas.append(f"P/L em nível razoável ({pl:.2f}).")
            elif pl >= 20: justificativas_negativas.append(f"P/L elevado ({pl:.2f}).")
            elif pl <= 0: justificativas_negativas.append(f"Empresa com prejuízo (P/L={pl:.2f}).")
        if pd.notna(pvp):
            if 0 < pvp < 1: justificativas_positivas.append(f"P/VP < 1 ({pvp:.2f}), pode estar descontada em relação ao VPA.")
            elif pvp >= 1 and pvp < 2: justificativas_positivas.append(f"P/VP razoável ({pvp:.2f}).")
            elif pvp >= 2: justificativas_negativas.append(f"P/VP pode ser considerado alto ({pvp:.2f}).")
            elif pvp <= 0 : justificativas_negativas.append(f"Patrimônio líquido negativo ou zero (P/VP={pvp:.2f}).")
        if pd.notna(dy):
            if dy >= 6: justificativas_positivas.append(f"Excelente Dividend Yield ({dy:.2f}%).")
            elif dy >= 4 and dy < 6: justificativas_positivas.append(f"Bom Dividend Yield ({dy:.2f}%).")
            elif dy < 2 and dy >=0: justificativas_negativas.append(f"Dividend Yield baixo ({dy:.2f}%).")
            elif dy <0 : justificativas_negativas.append(f"Dividend Yield negativo? ({dy:.2f}%).")
        if pd.notna(roe):
            if roe >= 20: justificativas_positivas.append(f"Excelente rentabilidade (ROE {roe:.2f}%).")
            elif roe >= 15 and roe < 20 : justificativas_positivas.append(f"Boa rentabilidade (ROE {roe:.2f}%).")
            elif roe < 10 and roe >=0 : justificativas_negativas.append(f"Rentabilidade (ROE {roe:.2f}%) pode ser melhorada.")
            elif roe < 0: justificativas_negativas.append(f"Rentabilidade negativa (ROE {roe:.2f}%).")
        if pd.notna(psg):
            if psg < 0.75: justificativas_positivas.append(f"Preço atrativo pelo Valor de Graham (P/VG {psg:.2f}).")
            elif psg >= 0.75 and psg < 1.2: justificativas_positivas.append(f"Preço razoável pelo Valor de Graham (P/VG {psg:.2f}).")
            elif psg >= 1.5: justificativas_negativas.append(f"Preço elevado pelo Valor de Graham (P/VG {psg:.2f}).")
        if pd.notna(var12m):
            if var12m > 15: justificativas_positivas.append(f"Boa valorização recente (Variação 12M: {var12m:.2f}%).")
            elif var12m < -15: justificativas_negativas.append(f"Desvalorização considerável recente (Variação 12M: {var12m:.2f}%).")
        if pd.notna(margem_liq):
            if margem_liq > 15: justificativas_positivas.append(f"Excelente margem líquida ({margem_liq:.2f}%).")
            elif margem_liq >= 5 and margem_liq < 15: justificativas_positivas.append(f"Margem líquida razoável ({margem_liq:.2f}%).")
            elif margem_liq < 5: justificativas_negativas.append(f"Margem líquida apertada ({margem_liq:.2f}%).")
        if pd.notna(p_ebit):
            if 0 < p_ebit < 10: justificativas_positivas.append(f"P/EBIT atrativo ({p_ebit:.2f}).")
            elif p_ebit >= 15: justificativas_negativas.append(f"P/EBIT elevado ({p_ebit:.2f}).")
            elif p_ebit <=0: justificativas_negativas.append(f"EBIT negativo ou zero (P/EBIT={p_ebit:.2f}).")
    except Exception as e:
        print(f"Erro ao gerar justificativas: {e}")

    print("\n--- Análise Detalhada (Baseada em Regras Heurísticas) ---")
    # Usar o predicao_texto_modelo para o cabeçalho
    print(f"O modelo classificou como: \"{predicao_texto_modelo}\". Observações com base em regras:")


    if justificativas_positivas:
        print("\n  Pontos Positivos Observados:")
        for just in justificativas_positivas:
            print(f"    ✅ {just}")
    else:
        print("\n  Nenhum ponto positivo destacado pelas regras heurísticas atuais para esta ação.")

    if justificativas_negativas:
        print("\n  Pontos Negativos / de Atenção Observados:")
        for just in justificativas_negativas:
            print(f"    ❌ {just}")
    else:
        print("\n  Nenhum ponto negativo/de atenção destacado pelas regras heurísticas atuais para esta ação.")


def recomendar_acao(ticker):
    print(f"Coletando dados para {ticker.upper()}...")
    resultado_scraper = coletar_indicadores(ticker)
    
    if isinstance(resultado_scraper, str):
        print(resultado_scraper)
        return
    elif resultado_scraper is None:
        print(f"Não foi possível coletar dados para {ticker.upper()}.")
        return

    dados_brutos, _ = resultado_scraper 
    print("Calculando feature 'preco_sobre_graham'...")
    dados_com_graham = calcular_preco_sobre_graham_para_recomendacao(dados_brutos)
    df_para_previsao_raw = pd.DataFrame([dados_com_graham])

    print("Preparando features para o modelo...")
    X_para_previsao = pd.DataFrame(columns=FEATURES_ESPERADAS_PELO_MODELO, index=[0])
    
    faltando_do_scraper = []
    for col in FEATURES_ESPERADAS_PELO_MODELO:
        if col in df_para_previsao_raw.columns:
            X_para_previsao.loc[0, col] = pd.to_numeric(df_para_previsao_raw.loc[0, col], errors='coerce')
        else:
             if col != 'preco_sobre_graham':
                 faltando_do_scraper.append(col)

    if faltando_do_scraper:
        print(f"Aviso: As seguintes features esperadas não foram encontradas nos dados do scraper (serão imputadas se possível): {faltando_do_scraper}")

    print("Carregando modelo e imputer treinados...")
    try:
        modelo, imputer = carregar_artefatos_modelo()
    except FileNotFoundError as e:
        print(e)
        return
    except Exception as e:
        print(f"Erro ao carregar artefatos do modelo: {e}")
        return

    print("Imputando valores ausentes (se houver)...")
    try:
        X_para_previsao_ordenado = X_para_previsao[FEATURES_ESPERADAS_PELO_MODELO]
        X_imputado_array = imputer.transform(X_para_previsao_ordenado)
        X_imputado_df = pd.DataFrame(X_imputado_array, columns=FEATURES_ESPERADAS_PELO_MODELO)
    except Exception as e:
        print(f"Erro durante a imputação de dados: {e}")
        return

    if X_imputado_df.isnull().any().any():
        print("\nAviso CRÍTICO: Mesmo após a imputação, ainda existem valores NaN.")
        print("Não é possível fazer uma recomendação confiável.")
        return
        
    print("Realizando previsão...")
    try:
        # pred_binaria = modelo.predict(X_imputado_df)[0] # Previsão binária 0 ou 1
        proba = modelo.predict_proba(X_imputado_df)[0]  # Probabilidades [prob_classe_0, prob_classe_1]
    except Exception as e:
        print(f"Um erro inesperado ocorreu durante a previsão: {e}")
        return

    # --- LÓGICA PARA RECOMENDAÇÃO GRANULAR BASEADA EM PROBABILIDADES ---
    prob_recomendada = proba[1] # Probabilidade da classe 1 (Recomendada)
    
    if prob_recomendada >= 0.75:
        recomendacao_final_texto = "FORTEMENTE RECOMENDADA para compra"
    elif prob_recomendada >= 0.60:
        recomendacao_final_texto = "RECOMENDADA para compra"
    elif prob_recomendada >= 0.50: # Limiar padrão do .predict()
        recomendacao_final_texto = "PARCIALMENTE RECOMENDADA (Neutro com viés positivo)"
    elif prob_recomendada >= 0.40:
        recomendacao_final_texto = "PARCIALMENTE NÃO RECOMENDADA (Neutro com viés negativo)"
    elif prob_recomendada >= 0.25:
        recomendacao_final_texto = "NÃO RECOMENDADA para compra"
    else: # prob_recomendada < 0.25
        recomendacao_final_texto = "FORTEMENTE NÃO RECOMENDADA para compra"
    # --------------------------------------------------------------------

    print("\n===================================================")
    print(f"Relatório de Recomendação para: {ticker.upper()}")
    print("===================================================")

    print(f"Resultado do Modelo: {recomendacao_final_texto.upper()}!") # Usar o texto granular
    print(f"Probabilidade (calculada pelo modelo): Não Recomendada={proba[0]:.2%}, Recomendada={proba[1]:.2%}")

    print("\n--- Indicadores Chave Utilizados na Análise (Valores que o Modelo Viu Após Imputação) ---")
    for feature_nome in FEATURES_CHAVE_PARA_EXIBIR_E_JUSTIFICAR:
        if feature_nome in X_imputado_df.columns:
            valor = X_imputado_df[feature_nome].iloc[0]
            if feature_nome in ['dividend_yield', 'roe', 'variacao_12m', 'margem_liquida']:
                print(f"  {feature_nome.replace('_',' ').capitalize()}: {valor:.2f}%")
            else:
                print(f"  {feature_nome.replace('_',' ').capitalize()}: {valor:.2f}")
        else:
            print(f"  {feature_nome.replace('_',' ').capitalize()}: Dado não disponível para exibição.")
            
    gerar_justificativas(X_imputado_df, recomendacao_final_texto) # Passar o texto da predição granular
    print("\n===================================================")

if __name__ == "__main__":
    ticker_input = input("Digite o ticker da ação (ex: PETR4): ").strip()
    if ticker_input:
        recomendar_acao(ticker_input)
    else:
        print("Nenhum ticker fornecido.")