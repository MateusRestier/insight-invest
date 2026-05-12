# 🏗️ Arquitetura do Sistema INSIGHT-INVEST

## Visão Geral

O INSIGHT-INVEST é um sistema completo de análise e recomendação de ações da B3 que integra:

- **Coleta automatizada** de dados fundamentalistas
- **Modelos de Machine Learning** (classificação + regressão)
- **Dashboard interativo** para visualização
- **Persistência em PostgreSQL**
- **Orquestração diária** automatizada

---

## Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE COLETA                             │
│                                                                     │
│  Investidor10 (Website)                                            │
│         ↓ (Web Scraping - BeautifulSoup)                           │
│  scraper_indicadores.py                                            │
│    • ThreadPoolExecutor (paralelo)                                 │
│    • 149 tickers da B3                                             │
│    • 31 indicadores fundamentalistas                               │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ INSERT/UPSERT
┌─────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE PERSISTÊNCIA                           │
│                                                                     │
│  PostgreSQL (Docker Container)                                      │
│  ├─ indicadores_fundamentalistas (PK: acao, data_coleta)          │
│  ├─ resultados_precos (PK: acao, data_previsao)                   │
│  └─ recomendacoes_acoes (UNIQUE: acao, data_recomendacao)         │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ SELECT para treino/predição
┌─────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE MACHINE LEARNING                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ classificador.py (RandomForestClassifier)                    │  │
│  │  • Objetivo: Prever bom desempenho futuro (Top 25%)         │  │
│  │  • Validação: TimeSeriesSplit + Hold-out temporal           │  │
│  │  • Tuning: RandomizedSearchCV                                │  │
│  │  • Output: modelo_classificador_desempenho.pkl              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ regressor_preco.py (RandomForestRegressor + tuning)          │  │
│  │  • Objetivo: Prever preço futuro N dias úteis à frente      │  │
│  │  • Estratégia: Modelos especializados por horizonte (BDay)  │  │
│  │  • Tuning: RandomizedSearchCV + TimeSeriesSplit             │  │
│  │  • Métricas: MAE, MSE, RMSE, R²                             │  │
│  │  • Output: Tabela resultados_precos (10 linhas/ação)        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ feature_engineering.py (módulo central de features)          │  │
│  │  • calcular_features_graham_estrito()                        │  │
│  │  • adicionar_delta_features() — momentum 7 dias             │  │
│  │  • adicionar_features_relativas() — posição vs. mercado     │  │
│  │  • FEATURES_REGRESSOR / FEATURES_CLASSIFICADOR (listas)     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ recomendador_acoes.py                                        │  │
│  │  • Carrega modelo treinado                                   │  │
│  │  • Coleta indicadores atuais (via scraper)                  │  │
│  │  • Gera probabilidades de recomendação                      │  │
│  │  • Justificativas heurísticas com filtros de sanidade       │  │
│  │  • Output: Tabela recomendacoes_acoes                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ Leitura para visualização
┌─────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE APRESENTAÇÃO                           │
│                                                                     │
│  Dashboard (Dash/Plotly + Bootstrap)                                │
│  ├─ pages/indicadores.py                                           │
│  │   • Top-10 ações por métrica                                    │
│  │   • Cards de recomendações                                      │
│  │   • KPIs do modelo (MAE, MSE, RMSE, R², MAPE)                  │
│  │   • Tabela Previsto × Real com filtros                         │
│  │   • Gráfico de distribuição de erro                            │
│  │                                                                 │
│  ├─ pages/previsoes.py                                             │
│  │   • Input: Ticker + Dias à frente                              │
│  │   • Barra de progresso em tempo real                           │
│  │   • Sistema de cache JSON (status + resultado)                 │
│  │   • Tabela com previsões multi-dia                             │
│  │                                                                 │
│  └─ pages/recomendador.py                                          │
│      • Input: Ticker                                               │
│      • Parecer textual formatado                                   │
│      • Cards responsivos com indicadores-chave                     │
│      • Análise detalhada (pontos positivos/negativos)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE ORQUESTRAÇÃO                           │
│                                                                     │
│  executar_tarefas_diarias.py (schedule)                            │
│  └─ Execução diária às 01:00                                       │
│     1. scraper_main() (~1-2 min)                                   │
│     2. executar_pipeline_regressor() (~3-5 min)                    │
│     3. recomendar_varias_acoes() (~2-4 min)                        │
│     4. criar_backup() (~1 min)                                     │
│                                                                     │
│  backup.py                                                          │
│  ├─ Backup: pg_dump via stdin/stdout                               │
│  └─ Restore: pg_restore via stdin/stdout                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Fluxo de Dados

### 1️⃣ Coleta (Diária às 01:00)

```
Investidor10
    ↓ (scraper_indicadores.py)
indicadores_fundamentalistas
    • UPSERT idempotente (ON CONFLICT)
    • ~149 tickers × 31 indicadores
    • Primary Key: (acao, data_coleta)
```

### 2️⃣ Treinamento (Sob Demanda)

```
indicadores_fundamentalistas
    ↓ (classificador.py)
    • Rotulagem por desempenho futuro (Top/Bottom 25%)
    • TimeSeriesSplit (5 folds)
    • RandomizedSearchCV (20 iterações)
    • Hold-out temporal (80/20)
    ↓
modelo_classificador_desempenho.pkl
```

### 3️⃣ Previsão de Preços (Diária)

```
indicadores_fundamentalistas
    ↓ (regressor_preco.py)
    • Loop: 1 dia até N dias
    • Modelo especializado por horizonte
    • merge_asof para preço futuro real
    ↓
resultados_precos
    • Campos: acao, data_previsao, preco_previsto, data_calculo
```

### 4️⃣ Geração de Recomendações (Diária)

```
Coleta atual (scraper)
    ↓ (recomendador_acoes.py)
    • Carrega modelo .pkl
    • Calcula preco_sobre_graham
    • Predict_proba() → probabilidades
    • Gera justificativas heurísticas
    ↓
recomendacoes_acoes
    • Campos: acao, recomendada, nao_recomendada, resultado, data_recomendacao
    • Upsert: ON CONFLICT (acao, data_recomendacao) DO UPDATE
    • Garante 1 registro por ação por dia (sem duplicatas)
```

### 5️⃣ Visualização (Tempo Real)

```
Dashboard (http://localhost:8050)
    ↓ (queries PostgreSQL)
    • Indicadores: TOP-10 + KPIs + Previsto×Real
    • Previsões: Cálculo sob demanda com progresso
    • Recomendador: Coleta + predição + justificativas
```

---

## Decisões de Design Importantes

### ✅ Por que Random Forest?

- **Dados tabulares** (não sequenciais)
- **Interpretabilidade** via `feature_importances_`
- **Robustez a outliers**
- **Não requer normalização**
- **Melhor para datasets moderados** (~134k registros)

### ✅ Por que TimeSeriesSplit?

- **Respeita ordem temporal**
- **Evita data leakage** (nunca treina com dados futuros)
- **Cada fold valida com dados posteriores ao treino**

### ✅ Por que merge_asof com direction='forward'?

- **Busca cotação real futura** (não predita)
- **Evita vazamento de informação**
- **Lida com datas faltantes** (pega próxima disponível)

### ✅ Por que modelos especializados por horizonte?

- **Padrões diferentes** para 1 dia vs 10 dias
- **Melhora acurácia** em cada horizonte
- **Facilita detecção de degradação** temporal

### ✅ Por que ProcessPoolExecutor para recomendações?

- **Verdadeiro paralelismo** (não bloqueado pelo GIL)
- **Scraping + modelo em paralelo**
- **Máximo aproveitamento de multi-core**

---

## Stack Tecnológico

| Camada | Tecnologia |
|--------|------------|
| **Backend** | Python 3.12 |
| **ML** | scikit-learn (RandomForest) |
| **Banco de Dados** | PostgreSQL 15 |
| **ORM/Driver** | psycopg2-binary |
| **Web Scraping** | BeautifulSoup4 + requests |
| **Dashboard** | Dash/Plotly + Bootstrap |
| **Orquestração** | schedule |
| **Paralelismo** | ThreadPoolExecutor + ProcessPoolExecutor |
| **Containerização** | Docker + docker-compose |

---

## Métricas de Performance

| Processo | Duração | Paralelismo | Memória |
|----------|---------|-------------|---------|
| **Scraping (149 tickers)** | 1-2 min | 7 threads | ~500 MB |
| **Classificador CV** | 5-10 min | multiprocessing | ~1.5 GB |
| **Regressor (10 dias)** | 3-5 min | sequencial | ~800 MB |
| **Recomendações (400+ tickers)** | 2-4 min | CPU count-1 | ~1.2 GB |
| **Backup** | ~1 min | pg_dump direto | ~100 MB |
| **Total Diário** | **7-12 min** | - | - |

---

## Volumes de Dados

| Entidade | Volume Estimado |
|----------|-----------------|
| **Tickers coletados** | 149 ações da B3 |
| **Indicadores por ação** | 31 métricas fundamentalistas |
| **Registros históricos** | ~134,100 (149 × ~900 dias) |
| **Previsões armazenadas** | ~1.34M (10 horizontes × 400+ tickers × 30+ datas) |
| **Tamanho do banco** | ~500 MB - 1 GB |

---

## Segurança e Confiabilidade

### Backup Automático
- **Frequência:** Diário às 01:00 (via container `scheduler`)
- **Método:** `pg_dump` direto (dentro do container) ou via `docker exec` (do host)
- **Armazenamento:** Volume Docker `backups` (arquivo `.dump`)
- **Restore:** Via `pg_restore` com stdin/stdout

### Idempotência
- **Scraper:** `ON CONFLICT (acao, data_coleta) DO UPDATE`
- **Regressor:** `ON CONFLICT (acao, data_previsao) DO UPDATE`
- **Recomendações:** `ON CONFLICT (acao, data_recomendacao) DO UPDATE`
- **Permite re-execução** sem duplicação de dados

### Validação Temporal
- **Hold-out:** 80/20 por data
- **Cross-Validation:** TimeSeriesSplit (5 folds)
- **Evita data leakage** em todos os estágios

---

## Próximos Passos / Roadmap

### Concluído (maio/2026)
- [x] Feature engineering centralizado (`src/models/feature_engineering.py`)
- [x] Delta features — momentum de preço e fundamentos (7 dias)
- [x] Features relativas ao mercado (posição cross-sectional diária)
- [x] Horizonte em dias úteis (BDay) no regressor e classificador
- [x] Hyperparameter tuning no regressor (RandomizedSearchCV + TimeSeriesSplit)
- [x] Deduplicação de `recomendacoes_acoes` (ON CONFLICT + data_recomendacao)
- [x] Multidia ativo em produção (executar_pipeline_multidia na API)
- [x] XAI via Gemini (explicação textual das recomendações)

### Curto Prazo
- [ ] Ajustar `janela_dias=14` quando banco tiver >2 meses (ver `docs/ML_EVOLUCAO.md`)
- [ ] SHAP values para interpretabilidade mais profunda
- [ ] Testes automatizados (pytest)

### Médio Prazo
- [ ] Análise técnica (RSI, MACD) como features adicionais
- [ ] Backtesting de estratégias
- [ ] Aumentar n_splits=5 e n_iter=30 quando banco tiver >3 meses

### Longo Prazo
- [ ] Avaliar Gradient Boosting (XGBoost/LightGBM) com >1 ano de dados
- [ ] Integração com outras bolsas (NASDAQ, NYSE)
- [ ] Análise de sentimento (NLP em notícias)