# Evolução dos Modelos de ML — O que mudar conforme o banco cresce

Este documento registra ajustes planejados nos modelos de ML que **não fazem sentido hoje** (poucos dados), mas devem ser feitos quando o histórico de `indicadores_fundamentalistas` for suficiente.

Contexto atual na criação deste documento (2026-05-12):
- ~28 dias de dados (2026-04-14 a 2026-05-11)
- ~148 ações scrapeadas diariamente
- ~4.100 linhas na tabela `indicadores_fundamentalistas`
- Erro médio do regressor: ~16,71% (antes das melhorias de maio/2026)

---

## Ajuste 1 — Aumentar janela das delta features

**Gatilho:** banco com mais de 2 meses de dados (~60 dias)

**Arquivos:**
- `src/models/feature_engineering.py` — função `adicionar_delta_features`
- `src/models/classificador.py` — chamada da função
- `src/models/regressor_preco.py` — chamada da função (em ambos os pipelines)

**O que mudar:**
```python
# Hoje (janela curta para não deixar metade do dataset sem cobertura):
adicionar_delta_features(df, janela_dias=7)

# Com >2 meses de dados:
adicionar_delta_features(df, janela_dias=14)

# Com >3 meses de dados (ideal):
adicionar_delta_features(df, janela_dias=21)
```

**Por que:** Com apenas 28 dias, uma janela de 14 dias deixaria as primeiras 2 semanas do dataset sem delta feature — metade dos dados ficaria com NaN e seria descartada no treino. Com 60+ dias, isso deixa de ser problema e janelas maiores capturam tendências mais longas e informativas (momentum de 2-3 semanas é mais relevante para fundamentos do que 7 dias).

---

## Ajuste 2 — Aumentar splits e iterações do tuning

**Gatilho:** banco com mais de 3 meses de dados (~400 linhas por ação)

**Arquivos:**
- `src/models/regressor_preco.py` — funções `executar_pipeline_regressor` e `executar_pipeline_multidia`
- `src/models/classificador.py` — função `treinar_avaliar_e_salvar_modelo`

**O que mudar no regressor:**
```python
# Hoje (poucos dados — mais splits esgotam o conjunto de treino):
n_splits = 3 if n_samples < 500 else 5
n_iter = 15

# Com >3 meses:
n_splits = 5
n_iter = 30
```

**O que mudar no classificador** (`treinar_avaliar_e_salvar_modelo`):
```python
# Hoje:
tscv = TimeSeriesSplit(n_splits=5)
search = RandomizedSearchCV(..., n_iter=20, ...)

# Com >3 meses, manter n_splits=5 mas aumentar n_iter:
search = RandomizedSearchCV(..., n_iter=40, ...)
```

**Por que:** Com 3 splits e dados escassos, cada fold de validação tem apenas ~6-8 dias. A estimativa de MAE fica ruidosa. Com 5 splits e dados suficientes, cada fold cobre ~3 semanas — avaliação muito mais confiável. Mais iterações no `RandomizedSearchCV` exploram melhor o espaço de hiperparâmetros.

---

## Ajuste 3 — Ativar `--sem-vazamento-temporal` no backfill

**Gatilho:** banco com mais de 6 meses de dados

**Arquivo:** uso do script `scripts/treinar_local_e_salvar.py`

**O que mudar:**
```bash
# Hoje (NÃO usar — dados insuficientes para treinar após remover os últimos 10 dias úteis):
python scripts/treinar_local_e_salvar.py --job regressor --n-dias 10 \
  --data-inicio 2026-04-14 --data-fim 2026-05-11

# Com >6 meses (seguro ativar):
python scripts/treinar_local_e_salvar.py --job regressor --n-dias 10 \
  --data-inicio <inicio> --data-fim <fim> --sem-vazamento-temporal
```

**Por que:** O flag remove do treino os exemplos cujo alvo (`preco_futuro_N_dias`) ainda não seria conhecido na `data_calculo`. Com 6+ meses de dados, mesmo removendo os últimos 10 dias úteis ainda sobram 5+ meses de treino — suficiente para o modelo generalizar. Antes disso, as datas iniciais do backfill ficariam com zero amostras de treino.

---

## Ajuste 4 — Expandir o grid de hiperparâmetros

**Gatilho:** banco com mais de 6 meses de dados

**Arquivos:**
- `src/models/regressor_preco.py`
- `src/models/classificador.py`

**O que mudar:**
```python
# Hoje (grid reduzido para ser rápido com poucos dados):
param_dist = {
    'n_estimators': [100, 200, 300],
    'max_depth': [5, 10, 15, None],
    'min_samples_leaf': [2, 5, 10],
    'max_features': ['sqrt', 'log2', 0.5],
}

# Com >6 meses (grid mais amplo):
param_dist = {
    'n_estimators': [200, 300, 500, 800],
    'max_depth': [5, 10, 15, 20, None],
    'min_samples_leaf': [1, 2, 5, 10],
    'max_features': ['sqrt', 'log2', 0.3, 0.5, 0.7],
    'min_samples_split': [2, 5, 10],
}
```

**Por que:** Com poucos dados, árvores profundas (`max_depth=None`, `min_samples_leaf=1`) sempre ganham no treino por overfitting — o grid atual as inclui mas elas raramente vencem na validação cruzada. Com mais dados, esses valores extremos podem ser genuinamente melhores e vale explorá-los. O grid expandido também inclui `min_samples_split` que hoje seria redundante.

---

## Ajuste 5 — Considerar trocar Random Forest por Gradient Boosting

**Gatilho:** banco com mais de 1 ano de dados

**Modelos candidatos:** `XGBoost`, `LightGBM`, `CatBoost`

**Por que considerar:** Random Forest é robusto com poucos dados (paralelo, menos sensível a hiperparâmetros). Gradient Boosting tende a ser mais preciso com datasets maiores mas requer mais tuning e é mais sensível a overfitting. Com 1 ano de dados (~50.000 linhas), a diferença começa a aparecer.

**Como avaliar:** Testar em paralelo com `cross_val_score` e comparar MAE médio. Trocar apenas se a diferença for consistente (>5% de melhora).

---

## Tabela resumo

| # | Ajuste | Gatilho | Arquivos |
|---|--------|---------|----------|
| 1 | `janela_dias=14` (depois `21`) | >2 meses | `feature_engineering.py` + chamadas |
| 2 | `n_splits=5`, `n_iter=30` | >3 meses | `regressor_preco.py`, `classificador.py` |
| 3 | `--sem-vazamento-temporal` no backfill | >6 meses | uso do script |
| 4 | Grid de hiperparâmetros expandido | >6 meses | `regressor_preco.py`, `classificador.py` |
| 5 | Avaliar Gradient Boosting | >1 ano | `regressor_preco.py`, `classificador.py` |

---

## Como verificar quanto dados há

```sql
-- Quantos dias de histórico existem?
SELECT
    MIN(data_coleta) AS primeiro_dia,
    MAX(data_coleta) AS ultimo_dia,
    COUNT(DISTINCT data_coleta) AS dias_com_dados,
    COUNT(*) AS total_linhas
FROM indicadores_fundamentalistas;
```
