"""
Migration: adiciona coluna data_recomendacao e constraint UNIQUE à tabela recomendacoes_acoes.
Execute uma única vez.
"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.db_connection import get_connection

conn = get_connection()
cur = conn.cursor()

print("Adicionando coluna data_recomendacao...")
cur.execute("""
    ALTER TABLE public.recomendacoes_acoes
    ADD COLUMN IF NOT EXISTS data_recomendacao DATE DEFAULT CURRENT_DATE
""")

print("Preenchendo registros antigos com NULL na coluna...")
cur.execute("""
    UPDATE public.recomendacoes_acoes
    SET data_recomendacao = CURRENT_DATE
    WHERE data_recomendacao IS NULL
""")

print("Removendo duplicatas existentes (mantém o registro de ctid máximo por acao+data)...")
cur.execute("""
    DELETE FROM public.recomendacoes_acoes a
    USING public.recomendacoes_acoes b
    WHERE a.ctid < b.ctid
      AND a.acao = b.acao
      AND a.data_recomendacao = b.data_recomendacao
""")
rows_deleted = cur.rowcount
print(f"  Registros duplicados removidos: {rows_deleted}")

print("Adicionando constraint UNIQUE (acao, data_recomendacao)...")
cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_acao_data_recomendacao'
        ) THEN
            ALTER TABLE public.recomendacoes_acoes
            ADD CONSTRAINT uq_acao_data_recomendacao UNIQUE (acao, data_recomendacao);
        END IF;
    END
    $$;
""")

print("Migration concluida com sucesso!")
cur.close()
conn.close()
