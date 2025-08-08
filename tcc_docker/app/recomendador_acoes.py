import os, pandas as pd, numpy as np, joblib, pyodbc
from scraper_indicadores import coletar_indicadores
from db_connection import get_connection
from concurrent.futures import ProcessPoolExecutor, as_completed

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
            # Filtro de Sanidade: P/L muito baixo pode ser um sinal de risco.
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
            # Filtro de Sanidade: ROE muito alto é suspeito.
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
            # Filtro de Sanidade: Margem muito alta é suspeita.
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

    # A lógica de exibição abaixo já está boa e não precisa de alteração.
    print("\n--- Análise Detalhada (Baseada em Regras Heurísticas) ---")
    if predicao_modelo == 1: # Se a predição binária for 1
        print("O modelo RECOMENDOU esta ação. Observações com base em regras:")
    else: # Se a predição binária for 0 (ou qualquer outro texto de não recomendação)
        # Ajuste para usar o texto granular que você criou
        print(f"O modelo classificou como: \"{predicao_modelo}\". Observações com base em regras:")

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

def _processar_ticker(ticker):
    """
    Função worker para processar um único ticker e inserir no banco.
    Retorna uma tupla (ticker, sucesso, mensagem).
    """
    try:
        resultado = coletar_indicadores(ticker)
        if not resultado or isinstance(resultado, str):
            return ticker, False, "scraper falhou"

        dados_brutos, _ = resultado
        dados = calcular_preco_sobre_graham_para_recomendacao(dados_brutos)
        df = pd.DataFrame([dados])

        # Prepara X_final
        X = pd.DataFrame(columns=FEATURES_ESPERADAS_PELO_MODELO, index=[0])
        for col in FEATURES_ESPERADAS_PELO_MODELO:
            if col in df.columns:
                X.loc[0, col] = pd.to_numeric(df.loc[0, col], errors='coerce')
        X_final = X.fillna(0)[FEATURES_ESPERADAS_PELO_MODELO]

        # Carrega o modelo e faz a previsão
        modelo = carregar_artefatos_modelo()
        proba = modelo.predict_proba(X_final)[0]
        prob_nao, prob_sim = proba[0], proba[1]
        # converte de numpy.float64 para float
        prob_nao = float(prob_nao)
        prob_sim = float(prob_sim)

        # Define o texto do resultado
        if prob_sim >= 0.75:
            texto = "FORTEMENTE RECOMENDADA PARA COMPRA!"
        elif prob_sim >= 0.60:
            texto = "RECOMENDADA PARA COMPRA"
        elif prob_sim >= 0.50:
            texto = "PARCIALMENTE RECOMENDADA (Viés positivo)"
        elif prob_sim >= 0.40:
            texto = "PARCIALMENTE NÃO RECOMENDADA (Viés negativo)"
        elif prob_sim >= 0.25:
            texto = "NÃO RECOMENDADA PARA COMPRA"
        else:
            texto = "FORTEMENTE NÃO RECOMENDADA PARA COMPRA"

        # Insere no PostgreSQL
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO public.recomendacoes_acoes
               (acao, recomendada, nao_recomendada, resultado)
            VALUES (%s, %s, %s, %s)
            """,
            (ticker, prob_sim, prob_nao, texto)
        )
        conn.commit()
        cur.close()
        conn.close()

        return ticker, True, f"{prob_sim:.2%}"
    except Exception as e:
        return ticker, False, str(e)

def recomendar_varias_acoes(conn):
    """
    Executa recomendação em paralelo para todos os tickers
    usando (n_cores - 1) workers.
    """
    tickers = [
        "AALR3","ABCB4","ABEV3","ADHM3","AERI3","AESB3","AFLT3","AGRO3","AGXY3","AHEB3","AHEB5","AHEB6","ALLD3","ALOS3","ALPA3",
        "ALPA4","ALPK3","ALUP11","ALUP3","ALUP4","AMAR3","AMBP3","AMER3","AMOB3","ANIM3","APER3","APTI3","APTI4","ARML3","ASAI3",
        "AURA33","AURE3","AVLL3","AZEV3","AZEV4","AZTE3","AZUL4","AZZA3","B3SA3","BAHI3","BALM3","BALM4","BAUH3","BAUH4","BAZA3",
        "BBAS3","BBDC3","BBDC4","BBML3","BBSE3","BDLL3","BDLL4","BEEF3","BEES3","BEES4","BFRE11","BFRE12","BGIP3","BGIP4","BHIA3",
        "BIDI11","BIDI3","BIDI4","BIOM3","BLAU3","BLUT3","BLUT4","BMEB3","BMEB4","BMGB4","BMIN3","BMIN4","BMKS3","BMOB3","BNBR3",
        "BOAS3","BOBR3","BOBR4","BPAC11","BPAC3","BPAC5","BPAN4","BPAR3","BPAT33","BPHA3","BRAP3","BRAP4","BRAV3","BRBI11","BRBI3",
        "BRBI4","BRFS3","BRGE11","BRGE12","BRGE3","BRGE5","BRGE6","BRGE7","BRGE8","BRIV3","BRIV4","BRKM3","BRKM5","BRKM6","BRML3",
        "BRPR3","BRQB3","BRSR3","BRSR5","BRSR6","BRST3","BSEV3","BSLI3","BSLI4","BTTL4","CALI3","CALI4","CAMB3","CAMB4","CAML3",
        "CASH3","CASN3","CASN4","CATA3","CATA4","CBAV3","CBEE3","CCXC3","CEAB3","CEBR3","CEBR5","CEBR6","CEDO3","CEDO4","CEEB3",
        "CEEB5","CEEB6","CEED3","CEED4","CEGR3","CEPE3","CEPE5","CEPE6","CESP3","CESP5","CESP6","CGAS3","CGAS5","CGRA3","CGRA4",
        "CIEL3","CLSA3","CLSC3","CLSC4","CMIG3","CMIG4","CMIN3","CMSA3","CMSA4","CNSY3","COCE3","COCE5","COCE6","COGN3","CORR3",
        "CORR4","CPFE3","CPLE3","CPLE5","CPLE6","CPRE3","CREM3","CRFB3","CRIV3","CRIV4","CRPG3","CRPG5","CRPG6","CSAB3","CSAB4",
        "CSAN3","CSED3","CSMG3","CSNA3","CSRN3","CSRN5","CSRN6","CSUD3","CTAX3","CTCA3","CTKA3","CTKA4","CTNM3","CTNM4","CTSA3",
        "CTSA4","CTSA8","CURY3","CVCB3","CXSE3","CYRE3","DASA3","DESK3","DEXP3","DEXP4","DIRR3","DMMO3","DMVF3","DOHL3","DOHL4",
        "DOTZ3","DTCY3","DTCY4","DXCO3","EALT3","EALT4","ECOR3","ECPR3","ECPR4","EEEL3","EEEL4","EGIE3","EKTR3","EKTR4","ELEK3",
        "ELEK4","ELET3","ELET5","ELET6","ELMD3","ELPL3","EMAE3","EMAE4","EMBR3","ENAT3","ENBR3","ENEV3","ENGI11","ENGI3","ENGI4",
        "ENJU3","ENMA3B","ENMA6B","ENMT3","ENMT4","EPAR3","EQPA3","EQPA5","EQPA6","EQPA7","EQTL3","ESPA3","ESTR3","ESTR4","ETER3",
        "EUCA3","EUCA4","EVEN3","EZTC3","FBMC3","FBMC4","FESA3","FESA4","FHER3","FICT3","FIEI3","FIGE3","FIGE4","FIQE3","FLEX3",
        "FLRY3","FNCN3","FRAS3","FRIO3","FRTA3","FTRT3B","G2DI33","GBIO33","GEPA3","GEPA4","GETT11","GETT3","GETT4","GFSA3","GGBR3",
        "GGBR4","GGPS3","GMAT3","GNDI3","GOAU3","GOAU4","GOLL4","GPAR3","GPIV33","GRAO3","GRND3","GSHP3","GUAR3","HAGA3","HAGA4",
        "HAPV3","HBOR3","HBRE3","HBSA3","HBTS3","HBTS5","HBTS6","HETA3","HETA4","HGTX3","HOOT3","HOOT4","HYPE3","IDVL3","IDVL4",
        "IFCM3","IGBR3","IGSN3","IGTA3","IGTI11","IGTI3","IGTI4","INEP3","INEP4","INNT3","INTB3","IRBR3","ISAE3","ISAE4","ITEC3",
        "ITSA3","ITSA4","ITUB3","ITUB4","JALL3","JBSS3","JFEN3","JHSF3","JOPA3","JOPA4","JSLG3","KEPL3","KLBN11","KLBN3","KLBN4",
        "KRSA3","LAME3","LAME4","LAND3","LAVV3","LCAM3","LEVE3","LHER3","LHER4","LIGT3","LINX3","LIPR3","LJQQ3","LOGG3","LOGN3",
        "LPSB3","LREN3","LTEL3B","LUPA3","LUXM3","LUXM4","LVTC3","LWSA3","MAPT3","MAPT4","MATD3","MDIA3","MDNE3","MEAL3","MELK3",
        "MERC3","MERC4","MGEL3","MGEL4","MGLU3","MILS3","MLAS3","MMXM3","MNDL3","MNPR3","MOAR3","MODL11","MODL3","MODL4","MOSI3",
        "MOTV3","MOVI3","MRFG3","MRSA3B","MRSA5B","MRSA6B","MRVE3","MSPA3","MSPA4","MSRO3","MTIG3","MTIG4","MTRE3","MTSA3","MTSA4",
        "MULT3","MWET3","MWET4","MYPK3","NAFG3","NAFG4","NATU3","NEMO3","NEMO4","NEMO5","NEMO6","NEOE3","NEXP3","NGRD3","NORD3",
        "NRTQ3","NTCO3","NUTR3","ODER3","ODER4","ODPV3","OFSA3","OGXP3","OIBR3","OIBR4","OMGE3","ONCO3","OPCT3","ORVR3","OSXB3",
        "PARD3","PATI3","PATI4","PCAR3","PCAR4","PDGR3","PDTC3","PEAB3","PEAB4","PETR3","PETR4","PETZ3","PFRM3","PGMN3","PINE3",
        "PINE4","PLAS3","PLPL3","PMAM3","PNVL3","PNVL4","POMO3","POMO4","PORT3","POSI3","POWE3","PPAR3","PPAR4","PPLA11","PRIO3",
        "PRNR3","PSSA3","PTBL3","PTCA11","PTCA3","PTNT3","PTNT4","QUAL3","QUSW3","QVQP3B","RADL3","RAIL3","RAIZ4","RANI3","RANI4",
        "RAPT3","RAPT4","RCSL3","RCSL4","RDNI3","RDOR3","REAG3","RECV3","REDE3","RENT3","RLOG3","RNEW11","RNEW3","RNEW4","ROMI3",
        "RPAD3","RPAD5","RPAD6","RPMG3","RSID3","RSUL3","RSUL4","SANB11","SANB3","SANB4","SAPR11","SAPR3","SAPR4","SBFG3","SBSP3",
        "SCAR3","SEDU3","SEER3","SEQL3","SGPS3","SHOW3","SHUL3","SHUL4","SIMH3","SLCE3","SLED3","SLED4","SMFT3","SMLS3","SMTO3",
        "SNSY3","SNSY5","SNSY6","SOJA3","SOMA3","SOND3","SOND5","SOND6","SPRT3B","SQIA3","SRNA3","STBP3","STKF3","STTR3","SULA11",
        "SULA3","SULA4","SUZB3","SYNE3","TAEE11","TAEE3","TAEE4","TASA3","TASA4","TCNO3","TCNO4","TCSA3","TECN3","TEKA3","TEKA4",
        "TELB3","TELB4","TEND3","TESA3","TFCO4","TGMA3","TIET11","TIET3","TIET4","TIMS3","TKNO3","TKNO4","TOKY3","TOTS3","TOYB3",
        "TOYB4","TPIS3","TRAD3","TRIS3","TTEN3","TUPY3","TXRX3","TXRX4","UCAS3","UGPA3","UNIP3","UNIP5","UNIP6","USIM3","USIM5",
        "USIM6","VALE3","VAMO3","VBBR3","VITT3","VIVA3","VIVR3","VIVT3","VIVT4","VLID3","VSPT3","VSPT4","VSTE3","VTRU3","VULC3",
        "VVEO3","WEGE3","WEST3","WHRL3","WHRL4","WIZC3","WLMM3","WLMM4","YDUQ3","ZAMP3"
    ]

    n_workers = max(os.cpu_count() - 1, 1)
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futuros = {executor.submit(_processar_ticker, t): t for t in tickers}
        for fut in as_completed(futuros):
            ticker, sucesso, msg = fut.result()
            status = "OK" if sucesso else "ERRO"
            print(f"{ticker}: {status} ({msg})")

def recomendar_acao(ticker):
    resultado_scraper = coletar_indicadores(ticker)
    
    if isinstance(resultado_scraper, str):
        print(resultado_scraper)
        return
    elif resultado_scraper is None:
        print(f"Não foi possível coletar dados para {ticker.upper()}.")
        return

    dados_brutos, _ = resultado_scraper
    dados_com_graham = calcular_preco_sobre_graham_para_recomendacao(dados_brutos)
    df_para_previsao_raw = pd.DataFrame([dados_com_graham])

    X_para_previsao = pd.DataFrame(columns=FEATURES_ESPERADAS_PELO_MODELO, index=[0])
    faltando_do_scraper = []
    for col in FEATURES_ESPERADAS_PELO_MODELO:
        if col in df_para_previsao_raw.columns:
            X_para_previsao.loc[0, col] = pd.to_numeric(df_para_previsao_raw.loc[0, col], errors='coerce')
        elif col != 'preco_sobre_graham':
            faltando_do_scraper.append(col)

    try:
        modelo = carregar_artefatos_modelo()
    except FileNotFoundError as e:
        print(e)
        return
    except Exception as e:
        print(f"Erro ao carregar modelo: {e}")
        return

    X_final = X_para_previsao[FEATURES_ESPERADAS_PELO_MODELO]

    try:
        proba = modelo.predict_proba(X_final)[0]
    except Exception as e:
        print(f"Erro durante a previsão: {e}")
        return

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

    print("\n===================================================")
    print(f"Relatório para: {ticker.upper()}")
    print("===================================================")
    print(f"Resultado do Modelo: {recomendacao_texto.upper()}!")
    print(f"Probabilidades - Não Recomendada: {proba[0]:.2%}, Recomendada: {proba[1]:.2%}")

    print("\n--- Indicadores Chave ---")
    for feat in FEATURES_CHAVE_PARA_EXIBIR_E_JUSTIFICAR:
        if feat in X_final.columns:
            val = X_final[feat].iloc[0]
            suf = '%' if feat in ['dividend_yield','roe','variacao_12m','margem_liquida'] else ''
            print(f"  {feat.replace('_',' ').capitalize()}: {val:.2f}{suf}")
        else:
            print(f"  {feat.replace('_',' ').capitalize()}: Não disponível")

    gerar_justificativas(X_final, recomendacao_texto)
    print("\n===================================================")

if __name__ == "__main__":
    print("Selecione a opção:")
    print("1 – Recomendar uma ação específica")
    print("2 – Recomendar todas as ações da lista")
    opcao = input("Opção (1/2): ").strip()

    if opcao == "1":
        ticker_input = input("Digite o ticker da ação (ex: PETR4): ").strip()
        if ticker_input:
            recomendar_acao(ticker_input)
        else:
            print("Nenhum ticker fornecido.")

    elif opcao == "2":
        conn = get_connection()
        recomendar_varias_acoes(conn)

    else:
        print("Opção inválida. Execute novamente e escolha 1 ou 2.")