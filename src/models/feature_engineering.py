"""
Módulo centralizado de feature engineering para os modelos de ML.

Funções disponíveis:
- calcular_features_graham_estrito: calcula VI de Graham e preco_sobre_graham
- adicionar_delta_features: variação percentual de indicadores-chave em janela de dias
- adicionar_features_relativas: posição relativa de cada ação vs. mediana diária do mercado
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Graham
# ---------------------------------------------------------------------------

def calcular_features_graham_estrito(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o VI de Graham e a feature preco_sobre_graham de forma estrita.
    VI_Graham só é calculado se LPA > 0 E VPA > 0.
    """
    df = df_input.copy()
    for col in ['lpa', 'vpa', 'cotacao']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            df[col] = np.nan

    df['vi_graham'] = np.nan
    df['preco_sobre_graham'] = np.nan
    condicao = (df['lpa'] > 0) & (df['vpa'] > 0)

    lpa_v = df.loc[condicao, 'lpa']
    vpa_v = df.loc[condicao, 'vpa']
    if not lpa_v.empty and not vpa_v.empty:
        df.loc[condicao, 'vi_graham'] = np.sqrt(22.5 * lpa_v * vpa_v)

    cond_vi = df['vi_graham'].notna() & (df['vi_graham'] != 0)
    df.loc[cond_vi, 'preco_sobre_graham'] = (
        df.loc[cond_vi, 'cotacao'] / df.loc[cond_vi, 'vi_graham']
    )
    return df


# ---------------------------------------------------------------------------
# Delta features (momentum de preço e fundamentos)
# ---------------------------------------------------------------------------

# Colunas usadas nas delta features
_COLS_DELTA = ['cotacao', 'pl', 'pvp', 'dividend_yield', 'roe']

def adicionar_delta_features(df: pd.DataFrame, janela_dias: int = 7) -> pd.DataFrame:
    """
    Para cada ação, calcula a variação percentual das colunas-chave em relação
    a `janela_dias` registros atrás (ordenados por data_coleta).

    Novas colunas: delta_cotacao_Nd, delta_pl_Nd, delta_pvp_Nd,
                   delta_dividend_yield_Nd, delta_roe_Nd
    onde N = janela_dias.

    Requer colunas: 'acao', 'data_coleta' e as colunas de _COLS_DELTA.
    Linhas sem histórico suficiente recebem NaN (o modelo simplesmente as ignora
    após o dropna() na preparação).
    """
    df = df.sort_values(['acao', 'data_coleta']).copy()
    suffix = f'{janela_dias}d'

    for col in _COLS_DELTA:
        if col not in df.columns:
            continue
        col_num = pd.to_numeric(df[col], errors='coerce')
        df[col] = col_num
        delta = (
            df.groupby('acao')[col]
              .pct_change(periods=janela_dias, fill_method=None)
        )
        df[f'delta_{col}_{suffix}'] = delta

    return df


# ---------------------------------------------------------------------------
# Features relativas ao mercado (posição cross-sectional)
# ---------------------------------------------------------------------------

_COLS_RELATIVAS = ['pl', 'pvp', 'roe', 'margem_liquida', 'dividend_yield']

def adicionar_features_relativas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada dia, calcula a razão entre o valor do indicador de cada ação
    e a mediana daquele indicador entre todas as ações naquele dia.

    Uma razão > 1 significa que a ação está ACIMA da mediana do mercado.
    Uma razão < 1 significa que está ABAIXO.

    Novas colunas: pl_vs_mercado, pvp_vs_mercado, roe_vs_mercado,
                   margem_liquida_vs_mercado, dividend_yield_vs_mercado
    """
    df = df.copy()
    for col in _COLS_RELATIVAS:
        if col not in df.columns:
            continue
        col_num = pd.to_numeric(df[col], errors='coerce')
        df[col] = col_num
        mediana_diaria = df.groupby('data_coleta')[col].transform('median')
        df[f'{col}_vs_mercado'] = col_num / (mediana_diaria.replace(0, np.nan) + 1e-9)

    return df


# ---------------------------------------------------------------------------
# Lista completa de features usada pelos modelos
# ---------------------------------------------------------------------------

FEATURES_BASE = [
    'pl', 'pvp', 'dividend_yield', 'payout', 'margem_liquida', 'margem_bruta',
    'margem_ebit', 'margem_ebitda', 'ev_ebit', 'p_ebit',
    'p_ativo', 'p_cap_giro', 'p_ativo_circ_liq', 'vpa', 'lpa',
    'giro_ativos', 'roe', 'roic', 'roa', 'patrimonio_ativos',
    'passivos_ativos', 'variacao_12m',
]

FEATURES_GRAHAM = ['preco_sobre_graham']

FEATURES_DELTA_7D = [
    'delta_cotacao_7d', 'delta_pl_7d', 'delta_pvp_7d',
    'delta_dividend_yield_7d', 'delta_roe_7d',
]

FEATURES_RELATIVAS = [
    'pl_vs_mercado', 'pvp_vs_mercado', 'roe_vs_mercado',
    'margem_liquida_vs_mercado', 'dividend_yield_vs_mercado',
]

# Features para o classificador (inclui fund_bad)
FEATURES_CLASSIFICADOR = FEATURES_BASE + FEATURES_GRAHAM + ['fund_bad'] + FEATURES_DELTA_7D + FEATURES_RELATIVAS

# Features para o regressor
FEATURES_REGRESSOR = FEATURES_BASE + FEATURES_GRAHAM + FEATURES_DELTA_7D + FEATURES_RELATIVAS


def aplicar_todas_features(df: pd.DataFrame, janela_delta: int = 7) -> pd.DataFrame:
    """
    Aplica o pipeline completo de feature engineering:
    1. Graham
    2. Delta features
    3. Features relativas ao mercado

    Retorna o DataFrame enriquecido, sem dropar linhas.
    """
    df = calcular_features_graham_estrito(df)
    df = adicionar_delta_features(df, janela_dias=janela_delta)
    df = adicionar_features_relativas(df)
    return df
