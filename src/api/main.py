import os
import sys
import threading
from pathlib import Path
from datetime import date

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from fastapi import FastAPI, BackgroundTasks, HTTPException, Security
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
        from src.models.classificador import treinar_modelo
        from src.models.regressor_preco import executar_pipeline_regressor
        treinar_modelo()
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)
