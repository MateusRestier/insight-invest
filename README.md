# 📊 Sistema Automatizado de Análise e Recomendação de Ações com Visual Analytics

Bem-vindo ao repositório do TCC **“Sistema Automatizado de Análise, Previsão e Recomendação de Ações com Visual Analytics”**!  
Este projeto integra coleta de dados fundamentalistas, modelagem (classificação e regressão), recomendações automatizadas e um dashboard interativo com persistência em PostgreSQL e orquestração de tarefas diárias.

---

## 🗂️ Sumário

- [📐 Arquitetura Geral](#-arquitetura-geral)
- [🛠️ Tecnologias](#-tecnologias)
- [📁 Estrutura do Repositório](#-estrutura-do-repositório)
- [🔄 Fluxo de Dados](#-fluxo-de-dados)
- [🗄️ Banco de Dados](#-banco-de-dados)
- [🧩 Módulos Principais](#-módulos-principais)
- [📈 Dashboard (Dash/Plotly)](#-dashboard-dashplotly)
- [🚀 Execução](#-execução)
  - [⚙️ Variáveis de Ambiente](#️-variáveis-de-ambiente)
  - [💻 Execução Local (sem Docker)](#-execução-local-sem-docker)
  - [🐳 Execução com Docker](#-execução-com-docker)
  - [🗃️ docker-compose (serviço de banco)](#️-docker-compose-serviço-de-banco)
- [🛡️ Backups e Restauração](#-backups-e-restauração)
- [⚡ Caches e Artefatos](#-caches-e-artefatos)
- [📝 Logs](#-logs)

---

## 📐 Arquitetura Geral


           +------------------------+
           |   Investidor10 (web)   |
           +-----------+------------+
                       |
                       | scraping
                       v
+----------------------+--------------------+
|      scraper_indicadores.py (coleta)      |
+----------------------+--------------------+
                       |
                       | INSERT/UPSERT
                       v
         +-------------------------------------+
         |          PostgreSQL (DB)            |
         |  - indicadores_fundamentalistas     |
         |  - resultados_precos                |
         |  - recomendacoes_acoes              |
         +----------+---------------+----------+
                    |               |
        leitura p/ treino        leitura p/ exibição
                    |               |
                    v               v
     +----------------------+   +----------------------------+
     |  classificador.py    |   |        Dashboard           |
     |  regressor_preco.py  |   |  (Dash: indicadores,       |
     +----------+-----------+   |   previsões e recomendações)|
                |               +----------------------------+
                | modelos/      ^
                v               |
        +-----------------+     |
        |  modelo/*.pkl   |     |
        +-----------------+     |
                                |
                                |
                                v
+---------------------------------------------------------------------+
| regressor_preco.py/recomendador_acoes.py (previsões/classificações) |
+---------------------------------------------------------------------+

           +----------------------------+
           | executar_tarefas_diarias   |
           | (orquestração diária)      |
           +----------------------------+

           +----------------------------+
           | backup.py (pg_dump/restore)|
           +----------------------------+


---

## 🛠️ Tecnologias

- 🐍 **Python 3.12**
- 📊 **Dash/Plotly** & `dash_bootstrap_components` (UI/UX do dashboard)
- 📈 `pandas`, `numpy`, `scikit-learn`
- 🐘 `psycopg2-binary` (PostgreSQL)
- 🌐 `BeautifulSoup4`, `requests` (scraping)
- ⏰ `schedule` (agendamento de tarefas diárias)
- 🐳 **Docker** & `docker-compose` (infraestrutura e banco)

---

## 📁 Estrutura do Repositório


tcc_docker/
├─ app/
│  ├─ backups/                     # dumps de banco (.dump)
│  ├─ dashboard/
│  │  ├─ assets/
│  │  │  └─ style.css              # estilos do dashboard
│  │  ├─ cache_results/            # resultados de previsões sob demanda (JSON)
│  │  ├─ cache_status/             # status/progresso de jobs (JSON)
│  │  ├─ pages/
│  │  │  ├─ indicadores.py         # página: top-10 métricas + previsto×real + KPIs
│  │  │  ├─ previsoes.py           # página: previsão multi-dia sob demanda (com progresso)
│  │  │  └─ recomendador.py        # página: recomendação pontual + cards de indicadores
│  │  ├─ app.py                    # bootstrap do Dash
│  │  └─ callbacks.py              # roteamento de abas + registro de callbacks
│  ├─ modelo/                      # artefatos de modelos (.pkl)
│  ├─ backup.py                    # pg_dump/restore
│  ├─ classificador.py             # treino do classificador
│  ├─ db_connection.py             # conexão PostgreSQL
│  ├─ executar_tarefas_diarias.py  # orquestração diária
│  ├─ recomendador_acoes.py        # grava recomendações no DB
│  ├─ regressor_preco.py           # treino/regressão de preço
│  └─ scraper_indicadores.py       # scraping de indicadores
├─ Dockerfile
├─ docker-compose.yml
└─ requirements.txt


---

## 🔄 Fluxo de Dados

1. **Coleta** (`scraper_indicadores.py`):  
   Scraping por ticker no Investidor10, normaliza indicadores e grava em `indicadores_fundamentalistas`.

2. **Modelagem**:
   - **Classificador** (`classificador.py`):  
     Lê históricos, deriva rótulos de desempenho futuro, treina `RandomForestClassifier` e salva modelo.
   - **Regressor de Preço** (`regressor_preco.py`):  
     Calcula alvos de preço futuro, treina `RandomForestRegressor` e grava previsões em `resultados_precos`.

3. **Recomendações** (`recomendador_acoes.py`):  
   Carrega modelo, coleta indicadores atuais, calcula probabilidade de “bom desempenho” e grava em `recomendacoes_acoes`.

4. **Orquestração Diária** (`executar_tarefas_diarias.py`):  
   Encadeia coleta → regressão multi-dia → recomendações em lote → backup (agendado para 01:00).

5. **Visualização** (`dashboard`):  
   Dashboard interativo com indicadores, previsões, recomendações e KPIs.

---

## 🗄️ Banco de Dados

**Tabelas principais:**

1. **indicadores_fundamentalistas**
    sql
    CREATE TABLE IF NOT EXISTS public.indicadores_fundamentalistas (
      acao                  TEXT        NOT NULL,
      data_coleta           DATE        NOT NULL,
      cotacao               NUMERIC,
      pl                    NUMERIC,
      pvp                   NUMERIC,
      roe                   NUMERIC,
      dividend_yield        NUMERIC,
      margem_liquida        NUMERIC,
      divida_liquida_patrimonio NUMERIC,
      lpa                   NUMERIC,
      vpa                   NUMERIC,
      variacao_12m          NUMERIC,
      PRIMARY KEY (acao, data_coleta)
    );
    
2. **resultados_precos**
    sql
    CREATE TABLE IF NOT EXISTS public.resultados_precos (
      acao           TEXT       NOT NULL,
      data_previsao  DATE       NOT NULL,
      preco_previsto NUMERIC    NOT NULL,
      data_coleta    DATE       NOT NULL,
      data_calculo   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (acao, data_previsao)
    );
    
3. **recomendacoes_acoes**
    sql
    CREATE TABLE IF NOT EXISTS public.recomendacoes_acoes (
      acao            TEXT        NOT NULL,
      prob_sim        NUMERIC     NOT NULL,
      prob_nao        NUMERIC     NOT NULL,
      resultado       TEXT        NOT NULL,
      data_insercao   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    

**Conexão:**  
Via `psycopg2` em `app/db_connection.py`, usando variáveis de ambiente:

- `DB_HOST` (padrão: localhost)
- `DB_NAME` (padrão: stocks)
- `DB_USER` (padrão: user)
- `DB_PASS` (padrão: password)
- `DB_PORT` (padrão: 5432)

---

## 🧩 Módulos Principais

- **scraper_indicadores.py**: Coleta e normaliza indicadores fundamentalistas por ação.
- **classificador.py**: Treina classificador de desempenho futuro.
- **recomendador_acoes.py**: Gera recomendações e grava no banco.
- **regressor_preco.py**: Treina regressor de preço futuro.
- **executar_tarefas_diarias.py**: Orquestra tarefas diárias.
- **backup.py**: Backup e restauração do banco de dados.

---

## 📈 Dashboard (Dash/Plotly)

Local: `app/dashboard`

- **app.py**: Inicializa o Dash (tema Bootstrap), expõe server e páginas.
- **callbacks.py**: Roteamento de abas e registro de callbacks.
- **pages/**:
  - `indicadores.py`: Ranking top-10, cards de recomendações, tabela previsto×real, KPIs, gráfico de erro.
  - `previsoes.py`: Previsão multi-dia sob demanda, barra de progresso.
  - `recomendador.py`: Recomendação pontual, parecer textual, cards de indicadores.
- **assets/style.css**: Estilos adicionais.

---

## 🚀 Execução

### ⚙️ Variáveis de Ambiente

Exemplo de `.env`:

DB_HOST=localhost
DB_NAME=stocks
DB_USER=user
DB_PASS=password
DB_PORT=5432

---

### 💻 Execução Local (sem Docker)

Pré-requisitos: Python 3.12 e PostgreSQL em execução.


# 1) Instalar dependências
pip install -r requirements.txt

# 2) Exportar variáveis de ambiente (Linux/macOS)
export DB_HOST=localhost DB_NAME=stocks DB_USER=user DB_PASS=password DB_PORT=5432
# (Windows - PowerShell)
# $env:DB_HOST="localhost"; $env:DB_NAME="stocks"; $env:DB_USER="user"; $env:DB_PASS="password"; $env:DB_PORT="5432"

# 3) Executar componentes
python app/scraper_indicadores.py
python app/classificador.py
python app/regressor_preco.py
python app/recomendador_acoes.py
python app/executar_tarefas_diarias.py
python app/dashboard/app.py


---

### 🐳 Execução com Docker


# Build da imagem
docker build -t tcc-app .

# Rodar o scraper dentro do container
docker run --rm \
  -e DB_HOST=host.docker.internal -e DB_NAME=stocks -e DB_USER=user -e DB_PASS=password -e DB_PORT=5432 \
  -v "$PWD/app/backups:/app/backups" \
  tcc-app python scraper_indicadores.py

# Rodar o dashboard na porta 8050
docker run --rm -p 8050:8050 \
  -e DB_HOST=host.docker.internal -e DB_NAME=stocks -e DB_USER=user -e DB_PASS=password -e DB_PORT=5432 \
  tcc-app python dashboard/app.py

---

### 🗃️ docker-compose (serviço de banco)


# Subir o banco
docker compose up -d db

# Logs do banco
docker compose logs -f db

# Parar
docker compose down

---

## 🛡️ Backups e Restauração

Gerenciados por `app/backup.py`.

- **Backup:** Cria dump via `pg_dump` e salva em `app/backups/` com timestamp.
- **Restauração:** Restaura um `.dump` existente para o banco ativo.

Exemplos:

# Criar backup
python app/backup.py --criar

# Restaurar (interativo)
python app/backup.py --restaurar

---

## ⚡ Caches e Artefatos

- **Modelos:** `app/modelo/*.pkl`
- **Dashboard – caches:**
  - `app/dashboard/cache_status/` (status/progresso dos jobs)
  - `app/dashboard/cache_results/` (resultados das previsões)
- **Backups:** `app/backups/*.dump`

---

## 📝 Logs

- Saída padrão dos scripts Python (stdout/stderr), com mensagens de progresso e resultados.
- Logs do banco via `docker compose logs db` quando executado com Compose.

---