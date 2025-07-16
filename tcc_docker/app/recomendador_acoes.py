import os, pandas as pd, numpy as np, joblib
from scraper_indicadores import coletar_indicadores

# Lista de features EXATAMENTE como o modelo foi treinado
FEATURES_ESPERADAS_PELO_MODELO = [
    'pl','pvp','dividend_yield','payout','margem_liquida','margem_bruta',
    'margem_ebit','margem_ebitda','ev_ebit','p_ebit',
    'p_ativo','p_cap_giro','p_ativo_circ_liq','vpa','lpa',
    'giro_ativos','roe','roic','roa','patrimonio_ativos',
    'passivos_ativos','variacao_12m','preco_sobre_graham','fund_bad'
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
    if not os.path.exists(modelo_path):
        raise FileNotFoundError(
            f"Modelo não encontrado em {modelo_path}. Execute o classificador.py primeiro."
        )
    modelo = joblib.load(modelo_path)
    print("Modelo carregado com sucesso.")
    return modelo


def gerar_justificativas(dados_acao_df, predicao_modelo):
    justificativas_positivas = []
    justificativas_negativas = []

    try:
        # Função auxiliar para extrair features numericamente de forma segura
        def get_numeric_feature(df, col_name):
            if col_name not in df.columns: # Verificação para evitar KeyErrors
                return np.nan
            return pd.to_numeric(df[col_name].iloc[0], errors='coerce')

        pl = get_numeric_feature(dados_acao_df, 'pl')
        pvp = get_numeric_feature(dados_acao_df, 'pvp')
        dy = get_numeric_feature(dados_acao_df, 'dividend_yield')
        roe = get_numeric_feature(dados_acao_df, 'roe')
        psg = get_numeric_feature(dados_acao_df, 'preco_sobre_graham')
        var12m = get_numeric_feature(dados_acao_df, 'variacao_12m')
        margem_liq = get_numeric_feature(dados_acao_df, 'margem_liquida')
        p_ebit = get_numeric_feature(dados_acao_df,'p_ebit')

        # ================== LÓGICA DE JUSTIFICATIVAS REFINADA COM FILTROS DE SANIDADE ==================

        # P/L (Preço/Lucro)
        if pd.notna(pl):
            if pl <= 0:
                justificativas_negativas.append(f"Empresa com prejuízo (P/L={pl:.2f}).")
            elif 0 < pl < 2:
                justificativas_negativas.append(f"P/L excessivamente baixo ({pl:.2f}), pode indicar alto risco ou distorções.")
            elif 2 <= pl < 10:
                justificativas_positivas.append(f"P/L baixo ({pl:.2f}), pode indicar subavaliação.")
            elif 10 <= pl < 20:
                justificativas_positivas.append(f"P/L em nível razoável ({pl:.2f}).")
            elif pl >= 20:
                justificativas_negativas.append(f"P/L elevado ({pl:.2f}).")

        # P/VP (Preço/Valor Patrimonial)
        if pd.notna(pvp):
            if pvp <= 0:
                justificativas_negativas.append(f"Patrimônio líquido negativo ou zero (P/VP={pvp:.2f}).")
            elif 0 < pvp < 1:
                justificativas_positivas.append(f"P/VP < 1 ({pvp:.2f}), pode estar descontada em relação ao VPA.")
            elif 1 <= pvp < 2:
                justificativas_positivas.append(f"P/VP razoável ({pvp:.2f}).")
            elif pvp >= 2:
                justificativas_negativas.append(f"P/VP pode ser considerado alto ({pvp:.2f}).")

        # Dividend Yield (em %)
        if pd.notna(dy):
            if dy >= 6: justificativas_positivas.append(f"Excelente Dividend Yield ({dy:.2f}%).")
            elif 4 <= dy < 6: justificativas_positivas.append(f"Bom Dividend Yield ({dy:.2f}%).")
            elif 0 <= dy < 2: justificativas_negativas.append(f"Dividend Yield baixo ({dy:.2f}%).")
            elif dy < 0: justificativas_negativas.append(f"Dividend Yield negativo ({dy:.2f}%), requer atenção.")

        # ROE (Retorno sobre o Patrimônio Líquido, em %)
        if pd.notna(roe):
            if roe > 50:
                justificativas_negativas.append(f"ROE extremamente alto ({roe:.2f}%), pode indicar distorção contábil ou patrimônio muito baixo.")
            elif 20 <= roe <= 50:
                justificativas_positivas.append(f"Excelente rentabilidade (ROE {roe:.2f}%).")
            elif 15 <= roe < 20:
                justificativas_positivas.append(f"Boa rentabilidade (ROE {roe:.2f}%).")
            elif 0 <= roe < 10:
                justificativas_negativas.append(f"Rentabilidade (ROE {roe:.2f}%) pode ser melhorada.")
            elif roe < 0:
                justificativas_negativas.append(f"Rentabilidade negativa (ROE {roe:.2f}%).")

        # Preco_Sobre_Graham
        if pd.notna(psg):
            if psg < 0.75: justificativas_positivas.append(f"Preço atrativo pelo Valor de Graham (P/VG {psg:.2f}).")
            elif 0.75 <= psg < 1.2: justificativas_positivas.append(f"Preço razoável pelo Valor de Graham (P/VG {psg:.2f}).")
            elif psg >= 1.5: justificativas_negativas.append(f"Preço elevado pelo Valor de Graham (P/VG {psg:.2f}).")

        # Variacao_12m (em %)
        if pd.notna(var12m):
            if var12m > 15: justificativas_positivas.append(f"Boa valorização recente (Variação 12M: {var12m:.2f}%).")
            elif var12m < -15: justificativas_negativas.append(f"Desvalorização considerável recente (Variação 12M: {var12m:.2f}%).")
        
        # Margem Líquida (em %)
        if pd.notna(margem_liq):
            if margem_liq > 40:
                justificativas_negativas.append(f"Margem líquida extremamente alta ({margem_liq:.2f}%), pode indicar lucro não recorrente.")
            elif 15 < margem_liq <= 40:
                justificativas_positivas.append(f"Excelente margem líquida ({margem_liq:.2f}%).")
            elif 5 <= margem_liq <= 15:
                justificativas_positivas.append(f"Margem líquida razoável ({margem_liq:.2f}%).")
            elif margem_liq < 5:
                justificativas_negativas.append(f"Margem líquida apertada ou negativa ({margem_liq:.2f}%).")

        # P/EBIT
        if pd.notna(p_ebit):
            if p_ebit <= 0:
                justificativas_negativas.append(f"EBIT negativo ou zero (P/EBIT={p_ebit:.2f}).")
            elif 0 < p_ebit < 10:
                justificativas_positivas.append(f"P/EBIT atrativo ({p_ebit:.2f}).")
            elif p_ebit >= 15:
                justificativas_negativas.append(f"P/EBIT elevado ({p_ebit:.2f}).")

    except Exception as e:
        print(f"Erro ao gerar justificativas: {e}")

    # Garantir que sempre haverá texto a ser retornado
    if not justificativas_positivas and not justificativas_negativas:
        justificativas_positivas.append("Não há justificativas disponíveis.")

    return "\n".join(justificativas_positivas + justificativas_negativas)




def recomendar_acao(ticker):
    print(f"Coletando dados para {ticker.upper()}...")
    resultado_scraper = coletar_indicadores(ticker)
    
    if isinstance(resultado_scraper, str):
        return resultado_scraper  # Retorna o erro de coleta se houver
    
    if resultado_scraper is None:
        return f"Não foi possível coletar dados para {ticker.upper()}."
    
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
        elif col != 'preco_sobre_graham':
            faltando_do_scraper.append(col)

    if faltando_do_scraper:
        print(f"Aviso: Features não encontradas no scraper: {faltando_do_scraper}")

    print("Carregando modelo treinado...")
    try:
        modelo = carregar_artefatos_modelo()
    except FileNotFoundError as e:
        return f"Erro: {e}"
    except Exception as e:
        return f"Erro ao carregar modelo: {e}"

    X_final = X_para_previsao[FEATURES_ESPERADAS_PELO_MODELO]

    print("Realizando previsão...")
    try:
        proba = modelo.predict_proba(X_final)[0]
    except Exception as e:
        return f"Erro durante a previsão: {e}"

    prob_recomendada = proba[1]
    if prob_recomendada >= 0.75:
        recomendacao_texto = "FORTEMENTE RECOMENDADA para compra"
    elif prob_recomendada >= 0.60:
        recomendacao_texto = "RECOMENDADA para compra"
    elif prob_recomendada >= 0.50:
        recomendacao_texto = "PARCIALMENTE RECOMENDADA (Viés positivo)"
    elif prob_recomendada >= 0.40:
        recomendacao_texto = "PARCIALMENTE NÃO RECOMENDADA (Viés negativo)"
    elif prob_recomendada >= 0.25:
        recomendacao_texto = "NÃO RECOMENDADA para compra"
    else:
        recomendacao_texto = "FORTEMENTE NÃO RECOMENDADA para compra"

    # Construir a explicação detalhada
    justificativas = gerar_justificativas(X_final, recomendacao_texto)

    # Retorna o resumo e a explicação completa
    resultado_resumido = f"O modelo classificou como: {recomendacao_texto}. Probabilidades - Não Recomendada: {proba[0]:.2%}, Recomendada: {proba[1]:.2%}"
    
    return f"{resultado_resumido}\n\nJustificativas:\n{justificativas}"


if __name__ == "__main__":
    ticker_input = input("Digite o ticker da ação (ex: PETR4): ").strip()
    if ticker_input:
        recomendar_acao(ticker_input)
    else:
        print("Nenhum ticker fornecido.")