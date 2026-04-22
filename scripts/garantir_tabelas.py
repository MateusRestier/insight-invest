import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.db_connection import get_connection


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS public.indicadores_fundamentalistas (
        acao varchar(10) NOT NULL,
        data_coleta date DEFAULT CURRENT_DATE NOT NULL,
        pl numeric(10, 2) NULL,
        psr numeric(10, 2) NULL,
        pvp numeric(10, 2) NULL,
        dividend_yield numeric(10, 2) NULL,
        payout numeric(10, 2) NULL,
        margem_liquida numeric(10, 2) NULL,
        margem_bruta numeric(10, 2) NULL,
        margem_ebit numeric(10, 2) NULL,
        margem_ebitda numeric(10, 2) NULL,
        ev_ebitda numeric(10, 2) NULL,
        ev_ebit numeric(10, 2) NULL,
        p_ebitda numeric(10, 2) NULL,
        p_ebit numeric(10, 2) NULL,
        p_ativo numeric(10, 2) NULL,
        p_cap_giro numeric(10, 2) NULL,
        p_ativo_circ_liq numeric(10, 2) NULL,
        vpa numeric(10, 2) NULL,
        lpa numeric(10, 2) NULL,
        giro_ativos numeric(10, 2) NULL,
        roe numeric(10, 2) NULL,
        roic numeric(10, 2) NULL,
        roa numeric(10, 2) NULL,
        div_liq_patrimonio numeric(10, 2) NULL,
        div_liq_ebitda numeric(10, 2) NULL,
        div_liq_ebit numeric(10, 2) NULL,
        div_bruta_patrimonio numeric(10, 2) NULL,
        patrimonio_ativos numeric(10, 2) NULL,
        passivos_ativos numeric(10, 2) NULL,
        liquidez_corrente numeric(10, 2) NULL,
        cotacao numeric(10, 2) NULL,
        variacao_12m numeric(10, 2) NULL,
        CONSTRAINT indicadores_fundamentalistas_pkey PRIMARY KEY (acao, data_coleta)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS public.recomendacoes_acoes (
        acao varchar(10) NOT NULL,
        recomendada numeric(5, 4) NOT NULL,
        nao_recomendada numeric(5, 4) NOT NULL,
        resultado varchar(100) NOT NULL,
        data_insercao timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS public.resultados_precos (
        id serial4 NOT NULL,
        acao varchar(10) NOT NULL,
        data_previsao date NOT NULL,
        preco_previsto numeric(14, 6) NOT NULL,
        data_coleta date DEFAULT CURRENT_DATE NOT NULL,
        data_calculo date DEFAULT CURRENT_DATE NOT NULL,
        CONSTRAINT resultados_precos_pkey PRIMARY KEY (id),
        CONSTRAINT unique_acao_data UNIQUE (acao, data_previsao),
        CONSTRAINT unique_acao_data_previsao UNIQUE (acao, data_previsao)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS public.resumos_diarios_ia (
        data_ref date PRIMARY KEY,
        resumo text NOT NULL,
        gerado_em timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
    """,
]


def garantir_tabelas(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            for ddl in DDL_STATEMENTS:
                cur.execute(ddl)
    finally:
        if own_conn and conn is not None:
            conn.close()


if __name__ == "__main__":
    garantir_tabelas()
    print("OK: tabelas garantidas.")

