# 🤖 Machine Learning - Detalhamento Técnico

## Visão Geral

O sistema utiliza **dois modelos de Random Forest**:

1. **Classificador:** Prediz se uma ação terá bom desempenho futuro (Top 25%)
2. **Regressor:** Prediz o preço futuro N dias à frente

Ambos implementam validação temporal rigorosa para evitar **data leakage**.

---

## 1️⃣ CLASSIFICADOR DE DESEMPENHO

### Objetivo

Classificar ações em duas categorias:
- **Classe 1 (Compra):** Ações no Top 25% de retorno futuro + qualidade fundamentalista
- **Classe 0 (Não Compra):** Ações no Bottom 25% ou com indicadores ruins

### Rotulagem Baseada em Desempenho Futuro

#### Processo de Rotulagem

```python
# 1. Calcular data futura alvo (N dias ÚTEIS à frente — BDay garante consistência)
from pandas.tseries.offsets import BDay
df['data_futura_alvo'] = df['data_coleta'] + BDay(10)

# 2. Buscar cotação futura real (merge_asof)
df_futuro = pd.merge_asof(
    left=df[['acao', 'data_futura_alvo']],
    right=df[['acao', 'data_coleta', 'cotacao']],
    left_on='data_futura_alvo',
    right_on='data_coleta',
    by='acao',
    direction='forward'  # pega próximo valor disponível
)

# 3. Calcular retorno futuro
df['retorno_futuro_10_dias'] = (
    (df['preco_futuro_10_dias'] - df['cotacao']) / df['cotacao']
)

# 4. Para cada dia, calcular quantis
for data in datas_unicas:
    dia_df = df[df['data_coleta'] == data]

    q_25 = dia_df['retorno_futuro_10_dias'].quantile(0.25)  # Bottom 25%
    q_75 = dia_df['retorno_futuro_10_dias'].quantile(0.75)  # Top 25%

    # Rótulo 0: Bottom 25%
    df.loc[(df['data_coleta'] == data) &
           (df['retorno_futuro_10_dias'] <= q_25), 'rotulo'] = 0

    # Rótulo 1: Top 25% + qualidade fundamentalista
    df.loc[(df['data_coleta'] == data) &
           (df['retorno_futuro_10_dias'] >= q_75) &
           (df['pl'] > 0) & (df['roe'] > 0), 'rotulo'] = 1

    # NaN: Meio 50% (descartado)
```

#### Por que Quantis por Data?

✅ **Adapta-se à volatilidade diária** (dias de alta vs baixa geral)
✅ **Compara ações entre si** naquele dia específico
✅ **Evita enviesamento** para períodos específicos
✅ **Robustez temporal** (não depende de valores absolutos)

### Features Engineering

Todo o feature engineering está centralizado em **`src/models/feature_engineering.py`**.

#### Features Utilizadas (33 no total — classificador / 32 no regressor)

```python
# ── Fundamentalistas base (22) ──────────────────────────────────────────
'pl',                    # Preço/Lucro
'pvp',                   # Preço/Valor Patrimonial
'dividend_yield',        # % de dividendos
'payout',                # % de distribuição
'margem_liquida',        # % margem líquida
'margem_bruta',          # % margem bruta
'margem_ebit',           # % margem EBIT
'margem_ebitda',         # % margem EBITDA
'ev_ebit',               # Enterprise Value / EBIT
'p_ebit',                # Preço / EBIT
'p_ativo',               # Preço / Ativos
'p_cap_giro',            # Preço / Capital de Giro
'p_ativo_circ_liq',      # Preço / Ativo Circulante Líquido
'vpa',                   # Valor Patrimonial por Ação
'lpa',                   # Lucro por Ação
'giro_ativos',           # Giro dos Ativos
'roe',                   # Retorno sobre Patrimônio
'roic',                  # Retorno sobre Capital Investido
'roa',                   # Retorno sobre Ativos
'patrimonio_ativos',     # Patrimônio / Ativos
'passivos_ativos',       # Passivos / Ativos
'variacao_12m',          # Variação dos últimos 12 meses

# ── Feature calculada — Value Investing (1) ──────────────────────────────
'preco_sobre_graham',    # Cotação / VI_Graham

# ── Delta features — momentum 7 dias (5) ────────────────────────────────
# Variação percentual de cada indicador em relação a 7 registros atrás.
# Dá ao modelo informação de TENDÊNCIA, não só valor absoluto.
'delta_cotacao_7d',
'delta_pl_7d',
'delta_pvp_7d',
'delta_dividend_yield_7d',
'delta_roe_7d',

# ── Features relativas ao mercado (5) ───────────────────────────────────
# Razão entre o valor da ação e a mediana diária de TODAS as ações.
# > 1 = acima da mediana do mercado naquele dia; < 1 = abaixo.
'pl_vs_mercado',
'pvp_vs_mercado',
'roe_vs_mercado',
'margem_liquida_vs_mercado',
'dividend_yield_vs_mercado',

# ── Indicador de qualidade — apenas no classificador (1) ─────────────────
'fund_bad'               # 1 se PL ≤ 0 ou ROE ≤ 0
```

#### Feature: Preço sobre Graham

```python
# Fórmula de Benjamin Graham (Value Investing)
VI_Graham = sqrt(22.5 × LPA × VPA)

# Aplicado apenas se LPA > 0 e VPA > 0
preco_sobre_graham = cotacao / VI_Graham
```

#### Features Delta (momentum)

```python
# src/models/feature_engineering.py — adicionar_delta_features()
df = df.sort_values(['acao', 'data_coleta'])
df['delta_cotacao_7d'] = df.groupby('acao')['cotacao'].pct_change(periods=7, fill_method=None)
# idem para pl, pvp, dividend_yield, roe
```

**Por que:** fundamentos mudam trimestralmente; o preço muda diariamente. Sem capturar tendência, o modelo vê apenas uma "foto" estática de cada ação, sem saber se está em alta ou em queda.

#### Features Relativas ao Mercado

```python
# src/models/feature_engineering.py — adicionar_features_relativas()
mediana_diaria = df.groupby('data_coleta')['pl'].transform('median')
df['pl_vs_mercado'] = df['pl'] / (mediana_diaria + 1e-9)
# idem para pvp, roe, margem_liquida, dividend_yield
```

**Por que:** uma margem líquida de 8% é boa para uma distribuidora, ruim para uma tech. Sem contexto cross-sectional, o modelo trata todos os setores no mesmo espaço de features.

**Interpretação:**
- `< 0.75`: Muito subavaliado (potencial de compra)
- `0.75 - 1.2`: Razoavelmente avaliado
- `> 1.5`: Sobreavaliado

#### Feature: fund_bad (Indicador de Qualidade)

```python
# Flag para empresas com indicadores ruins
fund_bad = 1 if (pl <= 0) or (roe <= 0) else 0

# Força rótulo 0 para ações de baixa qualidade
if fund_bad == 1:
    rotulo = 0  # Não compra
```

### Validação Temporal Rigorosa

#### Hold-out Temporal (80/20)

```python
# Separar por data (não aleatório!)
dates = df['data_coleta']
limite = dates.quantile(0.80)

# 80% dados históricos para treino/validação
X_train, y_train = X[dates <= limite], y[dates <= limite]

# 20% mais recentes para avaliação final
X_hold, y_hold = X[dates > limite], y[dates > limite]
```

**Importante:** O conjunto de hold-out **nunca é visto durante o tuning**.

#### Cross-Validation Temporal (TimeSeriesSplit)

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)

# Exemplo com 100 amostras:
# Fold 1: treina [0:20],   valida [20:40]
# Fold 2: treina [0:40],   valida [40:60]
# Fold 3: treina [0:60],   valida [60:80]
# Fold 4: treina [0:80],   valida [80:100]
# Fold 5: treina [0:100],  valida [100:120]

# Cada fold sempre treina com passado e valida com futuro
```

**Vantagem:** Simula produção real onde sempre predizemos o futuro.

### Hyperparameter Tuning

#### RandomizedSearchCV

```python
param_dist = {
    'n_estimators': [50, 100, 200, 300, 400, 500],
    'max_depth': [None, 5, 10, 20, 30],
    'min_samples_leaf': [1, 2, 5],
    'max_features': ['sqrt', 'log2', 0.3, 0.5, 0.7],
    'class_weight': ['balanced', None]
}

search = RandomizedSearchCV(
    RandomForestClassifier(random_state=42),
    param_distributions=param_dist,
    n_iter=20,              # 20 combinações aleatórias
    cv=tscv,                # validação cruzada temporal
    scoring='roc_auc',      # métrica de otimização
    n_jobs=-1,              # paraleliza
    random_state=42
)

search.fit(X_train, y_train)
best_model = search.best_estimator_
```

#### Por que max_features é importante?

- **`max_features='sqrt'`:** √n features por split (menos dependência de uma feature)
- **`max_features=0.5`:** 50% das features por split (força diversificação)

**Solução para "comprar no topo":** `max_features=0.5` reduz dependência de `variacao_12m`.

### Métricas de Avaliação

```python
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    classification_report,
    roc_auc_score
)

# Predição no hold-out (nunca visto antes)
y_pred = modelo.predict(X_hold)
y_proba = modelo.predict_proba(X_hold)[:, 1]

# Métricas
accuracy = accuracy_score(y_hold, y_pred)
conf_matrix = confusion_matrix(y_hold, y_pred)
roc_auc = roc_auc_score(y_hold, y_proba)

print(f"Acurácia: {accuracy:.2%}")
print(f"ROC-AUC: {roc_auc:.4f}")
print(classification_report(y_hold, y_pred))
```

**Métricas Típicas:**
- Acurácia: 65-75%
- ROC-AUC: 0.70-0.80
- Precision (Classe 1): 70-80%
- Recall (Classe 1): 60-70%

---

## 2️⃣ REGRESSOR DE PREÇOS

### Objetivo

Prever o preço de uma ação **N dias no futuro** usando indicadores fundamentalistas atuais.

### Pipeline de Regressão

#### Etapa 1: Adicionar Preço Futuro

```python
def adicionar_preco_futuro(df, n_dias):
    # BDay = dias úteis — garante que o alvo sempre cai num pregão,
    # eliminando a inconsistência de fins de semana/feriados
    from pandas.tseries.offsets import BDay
    df['data_futura_alvo'] = df['data_coleta'] + BDay(n_dias)

    # Por ação, buscar cotação futura
    def _por_acao(grp):
        merged = pd.merge_asof(
            left=grp[['data_futura_alvo']].sort_values('data_futura_alvo'),
            right=grp[['data_coleta', 'cotacao']],
            left_on='data_futura_alvo',
            right_on='data_coleta',
            direction='forward'
        )
        grp['preco_futuro_N_dias'] = merged['cotacao'].values
        return grp

    df = df.groupby('acao', group_keys=False).apply(_por_acao)
    return df
```

#### Etapa 2: Split Temporal

```python
# Se data_calculo for hoje (produção)
if data_calculo > ultima_data_disponivel:
    # Treina com todos os dados
    X_train = X
    y_train = y

# Se data_calculo for histórica (avaliação)
else:
    cutoff = pd.to_datetime(data_calculo)
    mask_train = dates < cutoff
    mask_test = dates == cutoff

    X_train, y_train = X[mask_train], y[mask_train]
    X_test, y_test = X[mask_test], y[mask_test]
```

#### Etapa 3: Treinamento com Busca de Hiperparâmetros

```python
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit

# Número de splits adaptativo ao volume de dados
n_splits = 3 if len(X_train) < 500 else 5
tscv = TimeSeriesSplit(n_splits=n_splits)

param_dist = {
    'n_estimators': [100, 200, 300],
    'max_depth': [5, 10, 15, None],
    'min_samples_leaf': [2, 5, 10],
    'max_features': ['sqrt', 'log2', 0.5],
}

search = RandomizedSearchCV(
    RandomForestRegressor(random_state=42),
    param_distributions=param_dist,
    n_iter=15,
    cv=tscv,
    scoring='neg_mean_absolute_error',
    n_jobs=-1,
    random_state=42,
)
search.fit(X_train, y_train)
model = search.best_estimator_
```

> **Nota:** ver `docs/ML_EVOLUCAO.md` para quando aumentar `n_splits` e `n_iter` conforme o banco cresce.

### Otimização Multi-Dia

#### Problema

Executar pipeline 10 vezes para prever 1, 2, 3... 10 dias:
- ❌ Carrega dados do banco 10 vezes
- ❌ Processa features 10 vezes
- ❌ Muito lento (~30 minutos)

#### Solução

```python
def executar_pipeline_multidia(max_dias=10, data_calculo=None, ...):
    # 1. Carrega dados UMA ÚNICA VEZ
    df = carregar_dados_do_banco()

    # 2. Calcula features UMA ÚNICA VEZ (pipeline completo)
    from src.models.feature_engineering import (
        calcular_features_graham_estrito,
        adicionar_delta_features,
        adicionar_features_relativas,
        FEATURES_REGRESSOR,
    )
    df = calcular_features_graham_estrito(df)
    df = adicionar_delta_features(df, janela_dias=7)
    df = adicionar_features_relativas(df)

    # 3. Loop leve por horizonte (1 modelo por horizonte)
    all_predictions = []
    for n in range(1, max_dias + 1):
        # 3.1. Adiciona preço futuro para este horizonte (BDay)
        df_n = adicionar_preco_futuro(df, n)

        # 3.2. Treina modelo com RandomizedSearchCV
        X_train, y_train = preparar_dados(df_n, n)
        search = RandomizedSearchCV(RandomForestRegressor(random_state=42), ...)
        search.fit(X_train, y_train)
        model = search.best_estimator_

        # 3.3. Prediz
        ultimos = X_train.groupby(acoes).tail(1)
        preds = model.predict(ultimos)

        # 3.4. Armazena (data alvo em dias úteis)
        from pandas.tseries.offsets import BDay
        all_predictions.append(pd.DataFrame({
            'acao': acoes,
            'data_previsao': (pd.Timestamp(data_calculo) + BDay(n)).date(),
            'preco_previsto': preds,
            'dias_a_frente': n
        }))

    # 4. Consolida tudo
    final = pd.concat(all_predictions)
    return final
```

**Resultado:** ~3-5 minutos (10x mais rápido!)

### Métricas de Avaliação

```python
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

# Predição
y_pred = model.predict(X_test)

# Métricas
mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, y_pred)

# Erro percentual médio
mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100

print(f"MAE: R$ {mae:.2f}")
print(f"RMSE: R$ {rmse:.2f}")
print(f"R²: {r2:.4f}")
print(f"MAPE: {mape:.2f}%")
```

**Métricas Observadas (maio/2026 — 28 dias de dados):**
- MAE CV: ~R$ 9.94
- R² treino: ~0.9888
- Melhores parâmetros encontrados: `n_estimators=300, min_samples_leaf=10, max_features=0.5, max_depth=15`

> À medida que o banco cresce, as métricas tendem a melhorar. Ver `docs/ML_EVOLUCAO.md` para os ajustes planejados.

---

## 3️⃣ RECOMENDADOR COM JUSTIFICATIVAS HEURÍSTICAS

### Níveis de Recomendação

```python
if prob_sim >= 0.75:
    texto = "FORTEMENTE RECOMENDADA PARA COMPRA!"
elif prob_sim >= 0.60:
    texto = "RECOMENDADA PARA COMPRA"
elif prob_sim >= 0.50:
    texto = "PARCIALMENTE RECOMENDADA (Viés positivo)"
elif prob_sim >= 0.40:
    texto = "PARCIALMENTE NÃO RECOMENDADA (Viés negativo)"
elif prob_sim >= 0.25:
    texto = "NÃO RECOMENDADA PARA COMPRA"
else:
    texto = "FORTEMENTE NÃO RECOMENDADA PARA COMPRA"
```

### Filtros de Sanidade (Value Investing)

#### P/L (Preço/Lucro)

```python
if pl <= 0:
    return "❌ Empresa com prejuízo"
elif 0 < pl < 2:
    return "❌ Excessivamente baixo (alto risco)"
elif 2 <= pl < 10:
    return "✅ Baixo, pode indicar subavaliação"
elif 10 <= pl < 20:
    return "✅ Nível razoável"
else:
    return "⚠️ Elevado"
```

#### ROE (Retorno sobre Patrimônio)

```python
if roe < 0:
    return "❌ Negativo (prejuízo)"
elif 0 <= roe < 10:
    return "⚠️ Pode melhorar"
elif 10 <= roe < 15:
    return "✅ Razoável"
elif 15 <= roe < 20:
    return "✅ Bom"
elif 20 <= roe <= 50:
    return "✅ Excelente"
else:
    return "❌ Extremamente alto (suspeito de distorção contábil)"
```

#### Dividend Yield

```python
if dy < 0:
    return "❌ Negativo"
elif 0 <= dy < 2:
    return "⚠️ Baixo"
elif 2 <= dy < 4:
    return "✅ Razoável"
elif 4 <= dy < 6:
    return "✅ Bom"
else:
    return "✅ Excelente"
```

---

## Prevenção de Data Leakage - Resumo

### ✅ Validação Temporal
- Hold-out por data (não aleatório)
- TimeSeriesSplit (sempre passado → futuro)

### ✅ merge_asof com direction='forward'
- Busca cotação futura real
- Não vaza informação do passado

### ✅ Separação de Tuning e Avaliação
- Tuning: Cross-validation no treino
- Avaliação: Hold-out nunca visto

### ✅ Sem Imputação de Dados
- Remove features com muitos missing
- Trabalha só com dados reais

---

## Feature Importance (Interpretabilidade)

```python
# Após treinar o modelo
importances = modelo.feature_importances_
feature_names = X.columns

# Ordenar por importância
indices = np.argsort(importances)[::-1]

print("Ranking de Features:")
for i, idx in enumerate(indices[:10], 1):
    print(f"{i}. {feature_names[idx]}: {importances[idx]:.4f}")
```

**Top Features Típicas (com 28 dias de dados):**
1. `preco_sobre_graham` (~15%)
2. `pl` (~12%)
3. `roe` (~10%)
4. `delta_cotacao_7d` (~9%) — nova feature de momentum
5. `variacao_12m` (~8%)
6. `margem_liquida` (~7%)

> Com mais dados, as features de delta e relativas tendem a ganhar importância relativa.

---

## Módulo Central de Feature Engineering

Todas as funções de feature engineering estão em **`src/models/feature_engineering.py`**:

| Função | Descrição |
|--------|-----------|
| `calcular_features_graham_estrito(df)` | VI de Graham e `preco_sobre_graham` |
| `adicionar_delta_features(df, janela_dias=7)` | Variação % de cotacao/pl/pvp/dy/roe em N dias |
| `adicionar_features_relativas(df)` | Razão vs. mediana diária do mercado |
| `aplicar_todas_features(df)` | Pipeline completo em uma chamada |
| `FEATURES_REGRESSOR` | Lista canônica de features do regressor (32) |
| `FEATURES_CLASSIFICADOR` | Lista canônica de features do classificador (33) |

---

## Conclusão

O sistema implementa Machine Learning com **rigor científico**:

✅ **Validação temporal** correta (TimeSeriesSplit + hold-out por data)
✅ **Feature engineering** centralizado: Graham + momentum + contexto de mercado
✅ **Tuning automatizado** com RandomizedSearchCV em ambos os modelos
✅ **Horizonte consistente** em dias úteis (BDay) para regressor e classificador
✅ **Deduplicação** de recomendações via ON CONFLICT (uma por ação por dia)
✅ **Interpretabilidade** via feature importances + XAI Gemini
✅ **Justificativas** baseadas em heurísticas de mercado
✅ **Métricas** adequadas para cada tipo de problema