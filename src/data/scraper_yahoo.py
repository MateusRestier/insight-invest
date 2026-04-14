"""
Coletor de indicadores fundamentalistas via yfinance (.info snapshot).

Pontos fortes  : margem_ebitda, payout, ev_ebitda, margens — dados diretos do Yahoo
Pontos fracos  : snapshot sem histórico, alguns campos ausentes para FIIs/bancos
"""

import os
import sys
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Union, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import yfinance as yf
from src.core.db_connection import get_connection


# ── Mapeamento yfinance .info → coluna DB ────────────────────────────────────
# Formato: chave_yfinance → (coluna_db, multiplicador_ou_None)
# multiplicador: None = usar valor direto | float = valor * multiplicador
#
# Notas de escala observadas em PETR4:
#   dividendYield  = 7.85   (já em %)          → multiplicador None
#   payoutRatio    = 0.389  (decimal 0-1)       → * 100
#   grossMargins   = 0.476  (decimal 0-1)       → * 100
#   returnOnEquity = 0.281  (decimal 0-1)       → * 100
#   debtToEquity   = 91.96  (dívida/PL * 100)  → / 100

MAPA_INFO = [
    # (chave_yfinance,                     coluna_db,             mult)
    ('trailingPE',                          'pl',                  None),
    ('priceToBook',                         'pvp',                 None),
    ('priceToSalesTrailing12Months',        'psr',                 None),
    ('dividendYield',                       'dividend_yield',      None),   # já em %
    ('payoutRatio',                         'payout',              100.0),
    ('grossMargins',                        'margem_bruta',        100.0),
    ('operatingMargins',                    'margem_ebit',         100.0),
    ('profitMargins',                       'margem_liquida',      100.0),
    ('ebitdaMargins',                       'margem_ebitda',       100.0),  # não existe no fundamentus
    ('returnOnEquity',                      'roe',                 100.0),
    ('returnOnAssets',                      'roa',                 100.0),
    ('bookValue',                           'vpa',                 None),
    ('trailingEps',                         'lpa',                 None),
    ('currentRatio',                        'liquidez_corrente',   None),
    ('enterpriseToEbitda',                  'ev_ebitda',           None),
    ('enterpriseToRevenue',                 'psr',                 None),   # fallback se priceToSales ausente
    ('regularMarketPrice',                  'cotacao',             None),
    ('debtToEquity',                        'div_bruta_patrimonio', 0.01), # /100
]

# Campos sem equivalente no yfinance → NULL
# ev_ebit, p_ebit, p_ebitda, p_ativo, p_cap_giro, p_ativo_circ_liq,
# div_liq_*, patrimonio_ativos, passivos_ativos, giro_ativos, roic


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(v, mult=None) -> Union[float, None]:
    try:
        f = float(v)
        return f * mult if mult is not None else f
    except (TypeError, ValueError):
        return None


def _variacao_12m(acao: str) -> Union[float, None]:
    try:
        t = yf.Ticker(acao + '.SA')
        hist = t.history(
            start=(datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d'),
            end=datetime.today().strftime('%Y-%m-%d'),
        )
        if hist.empty or len(hist) < 2:
            return None
        first = float(hist['Close'].iloc[0])
        if first == 0.0:
            return None
        return (float(hist['Close'].iloc[-1]) / first - 1.0) * 100.0
    except Exception:
        return None


# ── Funções públicas ──────────────────────────────────────────────────────────

def coletar_indicadores(acao: str) -> Union[Tuple[Dict, str], str]:
    """
    Coleta indicadores via yfinance .info.

    Retorna:
        (dados_dict, log_string)  — sucesso
        error_string              — falha
    """
    acao = acao.upper().strip()

    try:
        ticker_obj = yf.Ticker(acao + '.SA')
        info = ticker_obj.info
    except Exception as e:
        return f"❌ {acao} [yahoo] - erro ao buscar .info: {e}"

    if not info or info.get('regularMarketPrice') is None:
        return f"❌ {acao} [yahoo] - ticker não encontrado ou sem dados"

    dados: Dict = {'acao': acao}

    # Campos diretos via mapeamento (primeiro match não-None vence)
    preenchidos: set = set()
    for yf_key, db_col, mult in MAPA_INFO:
        if db_col in preenchidos:
            continue
        val = _safe_float(info.get(yf_key), mult)
        if val is not None:
            dados[db_col] = val
            preenchidos.add(db_col)
        elif db_col not in dados:
            dados[db_col] = None

    # Campos inexistentes no yfinance → NULL explícito
    sem_equivalente = [
        'ev_ebit', 'p_ebit', 'p_ebitda', 'p_ativo', 'p_cap_giro', 'p_ativo_circ_liq',
        'div_liq_patrimonio', 'div_liq_ebitda', 'div_liq_ebit',
        'patrimonio_ativos', 'passivos_ativos', 'giro_ativos', 'roic',
    ]
    for col in sem_equivalente:
        if col not in dados:
            dados[col] = None

    # variacao_12m
    dados['variacao_12m'] = _variacao_12m(acao)

    # Log
    linhas = [f"\n📊 Dados coletados (yahoo): {acao}"]
    for k, v in dados.items():
        linhas.append(f"  {k}: {v}")
    log_final = "\n".join(linhas)

    return dados, log_final


def salvar_no_banco(dados: Dict) -> None:
    dados["data_coleta"] = date.today()
    colunas      = ", ".join(dados.keys())
    placeholders = ", ".join(["%s"] * len(dados))
    update_exprs = [
        f"{col} = EXCLUDED.{col}"
        for col in dados if col not in ("acao", "data_coleta")
    ]
    sql = f"""
    INSERT INTO indicadores_fundamentalistas ({colunas})
    VALUES ({placeholders})
    ON CONFLICT (acao, data_coleta) DO UPDATE SET
    {", ".join(update_exprs)}
    """
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(sql, list(dados.values()))
        conn.commit(); cur.close(); conn.close()
        print("✅ Inserido/atualizado no banco.\n")
    except Exception as e:
        print("❌ Erro ao inserir no banco:", e)


def processar_acao(acao: str) -> None:
    resultado = coletar_indicadores(acao)
    if isinstance(resultado, tuple):
        dados, log = resultado
        print(log)
        salvar_no_banco(dados)
    else:
        print(resultado)
    time.sleep(0.5)


def main() -> None:
    acoes = [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "B3SA3", "ABEV3", "BBAS3", "BRFS3", "LREN3", "EGIE3",
        "JBSS3", "WEGE3", "RENT3", "GGBR4", "HAPV3", "CSAN3", "BRKM5", "MRVE3", "CPLE6", "RAIL3",
        "CMIG4", "ASAI3", "PRIO3", "EMBR3", "HYPE3", "ELET3", "ELET6", "ENBR3", "PETZ3", "ALPA4",
        "TIMS3", "AZUL4", "GOLL4", "NTCO3", "CVCB3", "DXCO3", "MGLU3", "CIEL3", "COGN3", "YDUQ3",
        "CRFB3", "BRML3", "SOMA3", "TOTS3", "LWSA3", "SUZB3", "KLBN11", "RAIZ4", "QUAL3", "SMTO3",
        "BPAC11", "CPFE3", "CYRE3", "MULT3", "EQTL3", "SLCE3", "VIVT3", "NEOE3", "MOVI3", "BEEF3",
        "ARZZ3", "CASH3", "TRPL4", "RRRP3", "VAMO3", "RANI3", "PARD3", "RECV3",
        "MEAL3", "TEND3", "MRFG3", "MDIA3", "TASA4", "GMAT3", "GFSA3", "BPAN4", "CEAB3",
        "DIRR3", "ENGI11", "GRND3", "IRBR3", "SEQL3", "UNIP6", "USIM5", "BRSR6", "SLED4", "STBP3",
        "CEPE5", "CBEE3", "MTSA4", "EZTC3", "AVLL3", "IGTI11", "BRPR3", "IGTA3", "TUPY3", "CGAS5",
        "FRAS3", "AERI3", "BLAU3", "LJQQ3", "LOGG3", "OFSA3", "ORVR3", "PNVL3",
        "POSI3", "POMO4", "PTBL3", "RAPT4", "SAPR4", "SBSP3", "TAEE11", "TGMA3", "TRIS3",
        "VIVA3", "VLID3", "WIZC3", "BRAP4", "BMIN3", "JHSF3", "EVEN3", "GUAR3", "HETA4", "VULC3",
        "MTRE3", "BMOB3", "ENAT3", "OIBR3", "CEGR3", "BALM4", "SMLS3", "SHOW3", "MODL11", "CBAV3",
        "ITSA4", "SANB11", "BBSE3", "RDOR3", "CXSE3", "PSSA3", "CEEB3", "TFCO4", "MRSA3B",
        "ALUP11", "UGPA3", "VBBR3", "ENEV3", "ISAE4", "EQPA3", "REDE3",
    ]

    print(f"\n🚀 Iniciando coleta via Yahoo Finance (4 threads)...\n")
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(processar_acao, a) for a in acoes]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print("❌ Erro em thread:", e)


if __name__ == "__main__":
    main()
