import atexit
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

import fundamentus
import yfinance as yf
from src.core.db_connection import get_connection


def _limpar_cache_fundamentus():
    """Remove o http_cache.sqlite criado pelo requests_cache do fundamentus."""
    cache = Path("http_cache.sqlite")
    if cache.exists():
        try:
            cache.unlink()
        except Exception:
            pass

atexit.register(_limpar_cache_fundamentus)


# ── Mapeamento Fundamentus → DB ───────────────────────────────────────────────
# Modos de parse (todos os valores chegam como string):
#   'pct'   : "6.6%"          → float(strip('%'))      → 6.6
#   'ratio' : "574", "071"    → float(s) / 100         → 5.74, 0.71
#   'direct': "49.03"         → float(s)               → 49.03
#   'fin'   : "1223390000000" → float(s)               → valor em R$

MAPA_DIRETO = [
    ('Cotacao',        'direct', 'cotacao'),
    ('PL',             'ratio',  'pl'),
    ('PVP',            'ratio',  'pvp'),
    ('PSR',            'ratio',  'psr'),
    ('Div_Yield',      'pct',    'dividend_yield'),
    ('PAtivos',        'ratio',  'p_ativo'),
    ('PCap_Giro',      'ratio',  'p_cap_giro'),
    ('PEBIT',          'ratio',  'p_ebit'),
    ('PAtiv_Circ_Liq', 'ratio',  'p_ativo_circ_liq'),
    ('EV_EBIT',        'ratio',  'ev_ebit'),
    ('EV_EBITDA',      'ratio',  'ev_ebitda'),
    ('Marg_EBIT',      'pct',    'margem_ebit'),
    ('Marg_Liquida',   'pct',    'margem_liquida'),
    ('Marg_Bruta',     'pct',    'margem_bruta'),
    ('Liquidez_Corr',  'ratio',  'liquidez_corrente'),
    ('ROIC',           'pct',    'roic'),
    ('ROE',            'pct',    'roe'),
    ('Div_Br_Patrim',  'ratio',  'div_bruta_patrimonio'),
    ('LPA',            'ratio',  'lpa'),
    ('VPA',            'ratio',  'vpa'),
    ('Giro_Ativos',    'ratio',  'giro_ativos'),
]

# Colunas sempre presentes (empresas e bancos)
COLUNAS_OBRIGATORIAS = ['Ativo', 'Patrim_Liq', 'Lucro_Liquido_12m']

# Colunas ausentes em bancos/financeiras (estrutura contábil diferente)
COLUNAS_NAO_BANCOS = ['Div_Liquida', 'EBIT_12m']


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_valor(raw, mode: str) -> Union[float, None]:
    """Converte string retornada pelo fundamentus para float."""
    if raw is None:
        return None
    s = str(raw).strip()
    try:
        if mode == 'pct':
            return float(s.replace('%', '').strip())
        elif mode == 'ratio':
            return float(s) / 100.0
        else:  # 'direct' ou 'fin'
            return float(s)
    except (ValueError, TypeError):
        return None


def _safe_div(a, b) -> Union[float, None]:
    """Divisão segura: retorna None se denominador for 0 ou qualquer valor None."""
    try:
        af, bf = float(a), float(b)
        return af / bf if bf != 0.0 else None
    except (TypeError, ValueError):
        return None


def _variacao_12m(acao: str) -> Union[float, None]:
    """
    Calcula variação de preço nos últimos 12 meses via yfinance.
    Retorna percentual (ex: 23.5 para +23.5%) ou None em qualquer falha.
    """
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
    Coleta indicadores fundamentalistas via biblioteca fundamentus.

    Retorna:
        (dados_dict, log_string)  — em caso de sucesso
        error_string              — em caso de falha

    Contrato idêntico ao scraper_investidor10.py.
    Campos sem equivalente no fundamentus (margem_ebitda, p_ebitda, payout)
    são gravados como None.
    """
    acao = acao.upper().strip()

    try:
        df = fundamentus.get_papel(acao)
    except Exception as e:
        return f"❌ {acao} - fundamentus erro: {e}"

    if df is None or df.empty:
        return f"❌ {acao} - ticker não encontrado no fundamentus"

    # Verifica apenas colunas obrigatórias (bancos não têm Div_Liquida/EBIT_12m)
    colunas_obrig = {c for c, _, _ in MAPA_DIRETO} | set(COLUNAS_OBRIGATORIAS)
    ausentes = colunas_obrig - set(df.columns)
    if ausentes:
        return f"❌ {acao} - colunas ausentes no fundamentus: {ausentes}"

    eh_banco = any(c not in df.columns for c in COLUNAS_NAO_BANCOS)

    dados: Dict = {'acao': acao}

    # Mapeamento direto
    for fnd_col, mode, db_col in MAPA_DIRETO:
        dados[db_col] = _parse_valor(df[fnd_col].iloc[0], mode)

    # Campos não disponíveis no fundamentus → NULL
    dados['margem_ebitda'] = None   # D&A indisponível
    dados['p_ebitda']      = None   # EBITDA indisponível
    dados['payout']        = None   # dividendos por ação indisponível

    # Valores financeiros brutos para cálculos
    ativo         = _parse_valor(df['Ativo'].iloc[0],             'fin')
    patrim_liq    = _parse_valor(df['Patrim_Liq'].iloc[0],        'fin')
    lucro_liq_12m = _parse_valor(df['Lucro_Liquido_12m'].iloc[0], 'fin')

    # Campos ausentes em bancos/financeiras → None
    div_liquida = _parse_valor(df['Div_Liquida'].iloc[0], 'fin') if not eh_banco else None
    ebit_12m    = _parse_valor(df['EBIT_12m'].iloc[0],    'fin') if not eh_banco else None

    # roa = Lucro Líquido / Ativo Total (em %)
    roa_raw = _safe_div(lucro_liq_12m, ativo)
    dados['roa'] = roa_raw * 100.0 if roa_raw is not None else None

    # Alavancagem (NULL para bancos — estrutura de dívida não aplicável)
    dados['div_liq_patrimonio'] = _safe_div(div_liquida, patrim_liq)
    dados['div_liq_ebit']       = _safe_div(div_liquida, ebit_12m)
    ebitda_aprox                = ebit_12m * 1.15 if ebit_12m is not None else None
    dados['div_liq_ebitda']     = _safe_div(div_liquida, ebitda_aprox)

    # Estrutura de capital (disponível para todos)
    dados['patrimonio_ativos'] = _safe_div(patrim_liq, ativo)
    passivo = (ativo - patrim_liq) if (ativo is not None and patrim_liq is not None) else None
    dados['passivos_ativos']   = _safe_div(passivo, ativo)

    # Variação 12 meses via yfinance
    dados['variacao_12m'] = _variacao_12m(acao)

    # Log formatado
    linhas = [f"\n📊 Dados coletados (fundamentus): {acao}"]
    for k, v in dados.items():
        linhas.append(f"  {k}: {v}")
    log_final = "\n".join(linhas)

    return dados, log_final


def salvar_no_banco(dados: Dict) -> None:
    """
    Insere ou atualiza os indicadores na tabela indicadores_fundamentalistas.
    ON CONFLICT (acao, data_coleta) → UPDATE de todas as colunas numéricas.
    """
    dados["data_coleta"] = date.today()

    colunas      = ", ".join(dados.keys())
    placeholders = ", ".join(["%s"] * len(dados))
    update_exprs = [
        f"{col} = EXCLUDED.{col}"
        for col in dados
        if col not in ("acao", "data_coleta")
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
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Inserido/atualizado no banco.\n")
    except Exception as e:
        print("❌ Erro ao inserir no banco:", e)


def processar_acao(acao: str) -> None:
    """Worker: coleta, loga e salva um ticker. Inclui sleep para rate limiting."""
    resultado = coletar_indicadores(acao)
    if isinstance(resultado, tuple):
        dados, log = resultado
        print(log)
        salvar_no_banco(dados)
    else:
        print(resultado)  # string de erro
    time.sleep(1)


def main() -> None:
    """Ponto de entrada. Executa coleta paralela com 4 threads."""
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

    print(f"\n🚀 Iniciando coleta via fundamentus (4 threads)...\n")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(processar_acao, acao) for acao in acoes]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print("❌ Erro em thread:", e)


if __name__ == "__main__":
    main()
