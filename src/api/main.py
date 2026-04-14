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
        calcular_preco_sobre_graham_para_recomendacao,
        carregar_artefatos_modelo,
        coletar_indicadores,
    )
    import pandas as pd

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

    return {
        "ticker": ticker,
        "resultado": resultado,
        "probabilidades": {
            "nao_recomendada": prob_nao,
            "recomendada": prob_sim,
        },
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
