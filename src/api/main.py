import os
import sys
import threading
from pathlib import Path
from datetime import date
import shutil

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import FastAPI, BackgroundTasks, HTTPException, Security, UploadFile, File
from starlette.middleware.wsgi import WSGIMiddleware
from fastapi.security.api_key import APIKeyHeader

# ── Auth ──────────────────────────────────────────────────────────────────────

API_KEY = os.getenv("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verificar_chave(key: str = Security(api_key_header)):
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=403, detail="API key inválida")
    return key

# ── Estado global de tarefas ──────────────────────────────────────────────────

_lock = threading.Lock()
_tarefa_em_andamento: dict = {"nome": None}

def _set_tarefa(nome: str | None):
    with _lock:
        _tarefa_em_andamento["nome"] = nome

def _get_tarefa() -> str | None:
    with _lock:
        return _tarefa_em_andamento["nome"]

# ── Workers ───────────────────────────────────────────────────────────────────

def _run_coletar():
    _set_tarefa("coletar")
    try:
        from src.data.scraper_orquestrador import main as scraper_main
        scraper_main()
    finally:
        _set_tarefa(None)

def _run_treinar():
    _set_tarefa("treinar")
    try:
        from src.models.classificador import executar_pipeline_classificador
        from src.models.regressor_preco import executar_pipeline_regressor
        executar_pipeline_classificador()
        executar_pipeline_regressor(n_dias=10, data_calculo=date.today())
    finally:
        _set_tarefa(None)

def _run_classificador():
    _set_tarefa("classificador")
    try:
        from src.models.classificador import executar_pipeline_classificador
        executar_pipeline_classificador()
    finally:
        _set_tarefa(None)

def _run_regressor():
    _set_tarefa("regressor")
    try:
        from src.models.regressor_preco import executar_pipeline_regressor
        executar_pipeline_regressor(n_dias=10, data_calculo=date.today())
    finally:
        _set_tarefa(None)

def _run_recomendar():
    _set_tarefa("recomendar")
    try:
        from src.core.db_connection import get_connection
        from src.models.recomendador_acoes import recomendar_varias_acoes
        conn = get_connection()
        recomendar_varias_acoes(conn)
    finally:
        _set_tarefa(None)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Insight Invest API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tarefas/status")
def status(_key: str = Security(verificar_chave)):
    tarefa = _get_tarefa()
    if tarefa:
        return {"em_andamento": True, "tarefa": tarefa}
    return {"em_andamento": False, "tarefa": None}

@app.post("/tarefas/coletar", status_code=202)
def coletar(background_tasks: BackgroundTasks, _key: str = Security(verificar_chave)):
    if _get_tarefa():
        raise HTTPException(status_code=409, detail=f"Tarefa '{_get_tarefa()}' já em andamento")
    background_tasks.add_task(_run_coletar)
    return {"aceito": True, "tarefa": "coletar"}

@app.post("/tarefas/treinar", status_code=202)
def treinar(background_tasks: BackgroundTasks, _key: str = Security(verificar_chave)):
    if _get_tarefa():
        raise HTTPException(status_code=409, detail=f"Tarefa '{_get_tarefa()}' já em andamento")
    background_tasks.add_task(_run_treinar)
    return {"aceito": True, "tarefa": "treinar"}

@app.post("/tarefas/treinar-classificador", status_code=202)
def treinar_classificador(background_tasks: BackgroundTasks, _key: str = Security(verificar_chave)):
    if _get_tarefa():
        raise HTTPException(status_code=409, detail=f"Tarefa '{_get_tarefa()}' já em andamento")
    background_tasks.add_task(_run_classificador)
    return {"aceito": True, "tarefa": "classificador"}

@app.post("/tarefas/treinar-regressor", status_code=202)
def treinar_regressor(background_tasks: BackgroundTasks, _key: str = Security(verificar_chave)):
    if _get_tarefa():
        raise HTTPException(status_code=409, detail=f"Tarefa '{_get_tarefa()}' já em andamento")
    background_tasks.add_task(_run_regressor)
    return {"aceito": True, "tarefa": "regressor"}

@app.post("/tarefas/recomendar", status_code=202)
def recomendar(background_tasks: BackgroundTasks, _key: str = Security(verificar_chave)):
    if _get_tarefa():
        raise HTTPException(status_code=409, detail=f"Tarefa '{_get_tarefa()}' já em andamento")
    background_tasks.add_task(_run_recomendar)
    return {"aceito": True, "tarefa": "recomendar"}

@app.post("/recomendacao/{ticker}")
def recomendacao_ticker(ticker: str, _key: str = Security(verificar_chave)):
    from src.models.recomendador_acoes import (
        FEATURES_ESPERADAS_PELO_MODELO,
        FEATURES_CHAVE_PARA_EXIBIR_E_JUSTIFICAR,
        calcular_preco_sobre_graham_para_recomendacao,
        carregar_artefatos_modelo,
        coletar_indicadores,
    )
    import pandas as pd
    import numpy as np

    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker inválido")

    resultado_scraper = coletar_indicadores(ticker)
    if isinstance(resultado_scraper, str) or resultado_scraper is None:
        raise HTTPException(status_code=422, detail=f"Falha ao coletar dados para {ticker}")

    dados_brutos, _ = resultado_scraper
    dados_com_graham = calcular_preco_sobre_graham_para_recomendacao(dados_brutos)
    df_para_previsao_raw = pd.DataFrame([dados_com_graham])

    x_previsao = pd.DataFrame(columns=FEATURES_ESPERADAS_PELO_MODELO, index=[0])
    for col in FEATURES_ESPERADAS_PELO_MODELO:
        if col in df_para_previsao_raw.columns:
            x_previsao.loc[0, col] = pd.to_numeric(df_para_previsao_raw.loc[0, col], errors="coerce")
    x_final = x_previsao.fillna(0)[FEATURES_ESPERADAS_PELO_MODELO]

    try:
        modelo = carregar_artefatos_modelo()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar modelo: {exc}") from exc

    try:
        proba = modelo.predict_proba(x_final)[0]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro durante previsão: {exc}") from exc

    prob_nao = float(proba[0])
    prob_sim = float(proba[1])

    if prob_sim >= 0.75:
        resultado = "FORTEMENTE RECOMENDADA para compra"
    elif prob_sim >= 0.60:
        resultado = "RECOMENDADA para compra"
    elif prob_sim >= 0.50:
        resultado = "PARCIALMENTE RECOMENDADA (Viés positivo)"
    elif prob_sim >= 0.40:
        resultado = "PARCIALMENTE NÃO RECOMENDADA (Viés negativo)"
    elif prob_sim >= 0.25:
        resultado = "NÃO RECOMENDADA para compra"
    else:
        resultado = "FORTEMENTE NÃO RECOMENDADA para compra"

    def _v(col):
        if col not in x_final.columns:
            return np.nan
        return pd.to_numeric(x_final[col].iloc[0], errors="coerce")

    pl = _v("pl")
    pvp = _v("pvp")
    dy = _v("dividend_yield")
    roe = _v("roe")
    psg = _v("preco_sobre_graham")
    var12m = _v("variacao_12m")
    margem_liq = _v("margem_liquida")
    p_ebit = _v("p_ebit")

    justificativas_positivas = []
    justificativas_negativas = []

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

    if pd.notna(pvp):
        if pvp <= 0:
            justificativas_negativas.append(f"Patrimônio líquido negativo ou zero (P/VP={pvp:.2f}).")
        elif 0 < pvp < 1:
            justificativas_positivas.append(f"P/VP < 1 ({pvp:.2f}), pode estar descontada em relação ao VPA.")
        elif 1 <= pvp < 2:
            justificativas_positivas.append(f"P/VP razoável ({pvp:.2f}).")
        elif pvp >= 2:
            justificativas_negativas.append(f"P/VP pode ser considerado alto ({pvp:.2f}).")

    if pd.notna(dy):
        if dy >= 6:
            justificativas_positivas.append(f"Excelente Dividend Yield ({dy:.2f}%).")
        elif 4 <= dy < 6:
            justificativas_positivas.append(f"Bom Dividend Yield ({dy:.2f}%).")
        elif 0 <= dy < 2:
            justificativas_negativas.append(f"Dividend Yield baixo ({dy:.2f}%).")
        elif dy < 0:
            justificativas_negativas.append(f"Dividend Yield negativo ({dy:.2f}%), requer atenção.")

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

    if pd.notna(psg):
        if psg < 0.75:
            justificativas_positivas.append(f"Preço atrativo pelo Valor de Graham (P/VG {psg:.2f}).")
        elif 0.75 <= psg < 1.2:
            justificativas_positivas.append(f"Preço razoável pelo Valor de Graham (P/VG {psg:.2f}).")
        elif psg >= 1.5:
            justificativas_negativas.append(f"Preço elevado pelo Valor de Graham (P/VG {psg:.2f}).")

    if pd.notna(var12m):
        if var12m > 15:
            justificativas_positivas.append(f"Boa valorização recente (Variação 12M: {var12m:.2f}%).")
        elif var12m < -15:
            justificativas_negativas.append(f"Desvalorização considerável recente (Variação 12M: {var12m:.2f}%).")

    if pd.notna(margem_liq):
        if margem_liq > 40:
            justificativas_negativas.append(f"Margem líquida extremamente alta ({margem_liq:.2f}%), pode indicar lucro não recorrente.")
        elif 15 < margem_liq <= 40:
            justificativas_positivas.append(f"Excelente margem líquida ({margem_liq:.2f}%).")
        elif 5 <= margem_liq <= 15:
            justificativas_positivas.append(f"Margem líquida razoável ({margem_liq:.2f}%).")
        elif margem_liq < 5:
            justificativas_negativas.append(f"Margem líquida apertada ou negativa ({margem_liq:.2f}%).")

    if pd.notna(p_ebit):
        if p_ebit <= 0:
            justificativas_negativas.append(f"EBIT negativo ou zero (P/EBIT={p_ebit:.2f}).")
        elif 0 < p_ebit < 10:
            justificativas_positivas.append(f"P/EBIT atrativo ({p_ebit:.2f}).")
        elif p_ebit >= 15:
            justificativas_negativas.append(f"P/EBIT elevado ({p_ebit:.2f}).")

    indicadores_chave = {}
    for feat in FEATURES_CHAVE_PARA_EXIBIR_E_JUSTIFICAR:
        val = _v(feat)
        indicadores_chave[feat] = None if pd.isna(val) else float(val)

    # ── Explicação XAI via Gemini ─────────────────────────────────────────────
    explicacao_ia = None
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            # Top-5 features mais importantes do modelo
            feature_names = FEATURES_ESPERADAS_PELO_MODELO
            importances = modelo.feature_importances_
            top_idx = importances.argsort()[::-1][:5]
            top_features = [
                f"{feature_names[i]} ({importances[i]*100:.1f}%): {_v(feature_names[i]):.2f}"
                for i in top_idx
                if not pd.isna(_v(feature_names[i]))
            ]

            positivos_str = "\n".join(f"- {j}" for j in justificativas_positivas) or "Nenhum"
            negativos_str = "\n".join(f"- {j}" for j in justificativas_negativas) or "Nenhum"
            top_str = "\n".join(f"- {f}" for f in top_features) or "Não disponível"

            prompt = f"""Você é um analista de investimentos em ações brasileiras. Analise a recomendação do modelo de machine learning para a ação {ticker} e escreva uma explicação clara e objetiva em português.

DADOS DO MODELO:
- Resultado: {resultado}
- Probabilidade de ser recomendada: {prob_sim*100:.1f}%

FEATURES MAIS IMPORTANTES PARA ESTA DECISÃO (nome: peso do modelo | valor atual):
{top_str}

PONTOS POSITIVOS IDENTIFICADOS:
{positivos_str}

PONTOS DE ATENÇÃO IDENTIFICADOS:
{negativos_str}

Escreva entre 3 e 5 frases explicando por que o modelo chegou a essa conclusão, conectando os indicadores mais relevantes com o resultado. Use linguagem acessível, sem jargões excessivos. Não repita os números já listados acima — apenas interprete-os. Não use markdown, listas ou títulos — apenas texto corrido.
"""
            import time
            from google import genai as google_genai
            from google.genai.errors import ClientError as _GeminiClientError
            _modelo_principal = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            client = google_genai.Client(api_key=gemini_key)

            # Busca todos os modelos disponíveis para esta chave que suportam generateContent
            _todos = [
                m.name.replace("models/", "")
                for m in client.models.list()
                if "generateContent" in (m.supported_actions or [])
            ]
            # Principal primeiro; demais em ordem retornada pela API (sem hardcode)
            _modelos = [_modelo_principal] + [m for m in _todos if m != _modelo_principal]

            for _modelo in _modelos:
                _tentou = False
                for _tentativa in range(2):
                    _tentou = True
                    try:
                        response = client.models.generate_content(
                            model=_modelo,
                            contents=prompt,
                        )
                        explicacao_ia = response.text.strip()
                        print(f"[XAI] Respondido por: {_modelo}")
                        break
                    except _GeminiClientError as _ce:
                        # 4xx (429 quota, 400 modality) — pula imediatamente, retry não resolve
                        print(f"[XAI] {_modelo} descartado (4xx): {_ce}")
                        _tentou = False
                        break
                    except Exception as _retry_err:
                        # 503 e similares — vale tentar novamente
                        print(f"[XAI] {_modelo} tentativa {_tentativa+1} falhou: {_retry_err}")
                        if _tentativa < 1:
                            time.sleep(3)
                if explicacao_ia:
                    break
        except Exception as _xai_err:
            print(f"[XAI] Erro ao chamar Gemini: {_xai_err}")
            explicacao_ia = None  # falha silenciosa — não quebra o endpoint

    return {
        "ticker": ticker,
        "resultado": resultado,
        "probabilidades": {
            "nao_recomendada": prob_nao,
            "recomendada": prob_sim,
        },
        "indicadores_chave": indicadores_chave,
        "justificativas_positivas": justificativas_positivas,
        "justificativas_negativas": justificativas_negativas,
        "explicacao_ia": explicacao_ia,
    }

@app.post("/modelo/upload")
def upload_modelo(
    arquivo: UploadFile = File(...),
    _key: str = Security(verificar_chave),
):
    nome_esperado = "modelo_classificador_desempenho.pkl"
    if arquivo.filename != nome_esperado:
        raise HTTPException(
            status_code=400,
            detail=f"Nome inválido. Envie exatamente '{nome_esperado}'.",
        )

    if not arquivo.filename.lower().endswith(".pkl"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .pkl")

    modelo_dir = _PROJECT_ROOT / "modelo"
    modelo_dir.mkdir(parents=True, exist_ok=True)
    destino = modelo_dir / nome_esperado

    try:
        with destino.open("wb") as f:
            shutil.copyfileobj(arquivo.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo: {exc}") from exc
    finally:
        arquivo.file.close()

    return {
        "ok": True,
        "arquivo": str(destino),
    }

# Dashboard embutido no mesmo serviço HTTP (Railway)
from src.dashboard.app import server as dash_server
app.mount("/", WSGIMiddleware(dash_server))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
