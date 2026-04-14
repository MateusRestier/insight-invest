"""
Orquestrador de coleta de indicadores fundamentalistas.

Ordem de preferência (fallback em cascata):
  1. Fundamentus  — principal, maior cobertura de ratios de valuation
  2. Yahoo Finance — preenche margem_ebitda, payout (ausentes no fundamentus)
  3. Investidor10  — último recurso, cobre campos residuais

Para cada campo, o primeiro valor não-None encontrado na ordem acima é mantido.
O resultado final é salvo UMA vez no banco (evita duplicatas).

Execução standalone:
    python src/data/scraper_orquestrador.py
"""

import os
import sys
import time
from pathlib import Path
from datetime import date
from typing import Dict, List, Optional
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import src.data.scraper_fundamentus  as s_fund
import src.data.scraper_yahoo        as s_yahoo
import src.data.scraper_investidor10 as s_inv10
from src.core.db_connection import get_connection


# ── Todas as colunas numéricas da tabela ─────────────────────────────────────
COLUNAS_INDICADORES = [
    "pl", "psr", "pvp", "dividend_yield", "payout",
    "margem_liquida", "margem_bruta", "margem_ebit", "margem_ebitda",
    "ev_ebitda", "ev_ebit", "p_ebitda", "p_ebit", "p_ativo",
    "p_cap_giro", "p_ativo_circ_liq", "vpa", "lpa", "giro_ativos",
    "roe", "roic", "roa",
    "div_liq_patrimonio", "div_liq_ebitda", "div_liq_ebit",
    "div_bruta_patrimonio", "patrimonio_ativos", "passivos_ativos",
    "liquidez_corrente", "cotacao", "variacao_12m",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _coletar_fonte(scraper_module, acao: str) -> Optional[Dict]:
    """Chama coletar_indicadores de um scraper e retorna o dict ou None."""
    try:
        resultado = scraper_module.coletar_indicadores(acao)
        if isinstance(resultado, tuple):
            return resultado[0]
    except Exception as e:
        print(f"  ⚠ [{scraper_module.__name__.split('.')[-1]}] erro em {acao}: {e}")
    return None


def _mesclar(base: Dict, fallback: Dict) -> Dict:
    """
    Preenche campos None em `base` com valores de `fallback`.
    Metadados (acao, data_coleta) nunca são sobrescritos.
    """
    for col in COLUNAS_INDICADORES:
        if base.get(col) is None and fallback.get(col) is not None:
            base[col] = fallback[col]
    return base


def _dict_vazio(acao: str) -> Dict:
    d = {"acao": acao}
    for col in COLUNAS_INDICADORES:
        d[col] = None
    return d


def _contar_nulos(dados: Dict) -> int:
    return sum(1 for col in COLUNAS_INDICADORES if dados.get(col) is None)


# ── Função principal de coleta orquestrada ───────────────────────────────────

def coletar_com_fallback(acao: str) -> Dict:
    """
    Coleta indicadores para um ticker usando fallback em cascata:
    Fundamentus → Yahoo → Investidor10.

    Retorna dict com todas as colunas (None para campos não encontrados em nenhuma fonte).
    """
    acao = acao.upper().strip()
    dados = _dict_vazio(acao)

    fontes = [
        ("fundamentus",  s_fund),
        ("yahoo",        s_yahoo),
        ("investidor10", s_inv10),
    ]

    for nome, modulo in fontes:
        nulos_antes = _contar_nulos(dados)
        if nulos_antes == 0:
            break  # todos os campos preenchidos

        print(f"  [{nome}] coletando {acao}...")
        parcial = _coletar_fonte(modulo, acao)
        if parcial:
            dados = _mesclar(dados, parcial)
            nulos_depois = _contar_nulos(dados)
            preenchidos  = nulos_antes - nulos_depois
            print(f"  [{nome}] {acao}: +{preenchidos} campos ({nulos_depois} nulos restantes)")
        else:
            print(f"  [{nome}] {acao}: sem dados")

    return dados


def salvar_no_banco(dados: Dict) -> None:
    dados_save = dict(dados)
    dados_save["data_coleta"] = date.today()
    colunas      = ", ".join(dados_save.keys())
    placeholders = ", ".join(["%s"] * len(dados_save))
    update_exprs = [
        f"{col} = EXCLUDED.{col}"
        for col in dados_save if col not in ("acao", "data_coleta")
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
        cur.execute(sql, list(dados_save.values()))
        conn.commit(); cur.close(); conn.close()
        print(f"  ✅ {dados_save['acao']} salvo no banco.\n")
    except Exception as e:
        print(f"  ❌ Erro ao salvar {dados_save.get('acao')}: {e}")


def processar_acao(acao: str) -> None:
    print(f"\n{'─'*50}")
    print(f"  Processando: {acao}")
    dados = coletar_com_fallback(acao)
    nulos_final = _contar_nulos(dados)
    print(f"  → Resultado final: {len(COLUNAS_INDICADORES) - nulos_final}/{len(COLUNAS_INDICADORES)} campos preenchidos")
    salvar_no_banco(dados)
    time.sleep(0.5)  # rate limiting geral


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

    print(f"\n🚀 Orquestrador iniciado — {len(acoes)} tickers (sequencial com fallback)\n")
    print("Ordem de fontes: Fundamentus → Yahoo Finance → Investidor10\n")

    # Sequencial (não paralelo) para respeitar rate limits das 3 fontes simultaneamente
    for acao in acoes:
        try:
            processar_acao(acao)
        except Exception as e:
            print(f"❌ Erro inesperado em {acao}: {e}")

    print("\n✅ Coleta orquestrada concluída.")


if __name__ == "__main__":
    main()
