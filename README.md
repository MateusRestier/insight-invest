# 📊 Scraping de Indicadores de Ações com Python + PostgreSQL + Docker

Este projeto realiza a coleta de dados fundamentalistas de ações listadas na B3, diretamente do site [Investidor10](https://investidor10.com.br), e armazena os dados em um banco PostgreSQL via Docker.

---

## 🚀 Funcionalidades

- Scraping de +150 ações populares da B3
- Extração de:
  - Indicadores fundamentalistas (P/L, ROE, EV/EBITDA etc.)
  - Cotação atual da ação
  - Variação nos últimos 12 meses
- Inserção automática no banco PostgreSQL
- Rodando com paralelismo via `ThreadPoolExecutor`
- Executável via Docker Compose

---

## 🧱 Tecnologias Utilizadas

- Python 3.12
- BeautifulSoup4
- Requests
- psycopg2-binary
- Docker e Docker Compose
- PostgreSQL 15

---

## 📦 Estrutura do Projeto

```
PRIVATE-TCC/
├─tcc_docker/
  ├── Dockerfile
  ├── docker-compose.yml
  ├── requirements.txt
  └── app/
      ├── analisador_graham_db.py
      ├── backup.py
      ├── backups/
      │   └── backup_2025-06-10_18-37-29.dump
      ├── classificador.py
      ├── db_connection.py
      ├── executar_tudo.py
      ├── modelo/
      │   ├── imputer.pkl
      │   └── modelo_classificador_desempenho.pkl
      ├── recomendador_acoes.py
      ├── regressor_preco.py
      └── scraper_indicadores.py
```

---

## ⚙️ Como executar no novo PC

### 1. Instale:

- Python 3.12.x — [https://python.org](https://python.org)
- Docker Desktop — [https://docker.com](https://docker.com)
- Git (opcional) — [https://git-scm.com](https://git-scm.com)

### 2. Clone o repositório

```bash
git clone https://github.com/seu-usuario/seu-repo.git
cd PRIVATE-TCC/tcc_docker
```

### 3. Suba o banco com Docker

```bash
docker compose up -d
```

Ou, se preferir, clique em ▶️ **Start** no Docker Desktop na aba Containers.

---

## 🐍 Rodar o Scraper

Execute o seguinte comando para rodar o scraping:

```bash
docker compose run scraper python scraper_indicadores.py
```

Isso irá:

- Coletar os dados das ações
- Inserir na tabela `indicadores_fundamentalistas`

---

## 🗃 Estrutura da Tabela no Banco

A tabela `indicadores_fundamentalistas` deve conter:

```sql
CREATE TABLE indicadores_fundamentalistas (
    acao VARCHAR(10),
    data_coleta DATE,
    pl NUMERIC,
    psr NUMERIC,
    pvp NUMERIC,
    dividend_yield NUMERIC,
    payout NUMERIC,
    margem_liquida NUMERIC,
    margem_bruta NUMERIC,
    margem_ebit NUMERIC,
    margem_ebitda NUMERIC,
    ev_ebitda NUMERIC,
    ev_ebit NUMERIC,
    p_ebitda NUMERIC,
    p_ebit NUMERIC,
    p_ativo NUMERIC,
    p_cap_giro NUMERIC,
    p_ativo_circ_liq NUMERIC,
    vpa NUMERIC,
    lpa NUMERIC,
    giro_ativos NUMERIC,
    roe NUMERIC,
    roic NUMERIC,
    roa NUMERIC,
    div_liq_patrimonio NUMERIC,
    div_liq_ebitda NUMERIC,
    div_liq_ebit NUMERIC,
    div_bruta_patrimonio NUMERIC,
    patrimonio_ativos NUMERIC,
    passivos_ativos NUMERIC,
    liquidez_corrente NUMERIC,
    cotacao NUMERIC,
    variacao_12m NUMERIC,
    PRIMARY KEY (acao, data_coleta)
);
```

---

## 🧠 Observações

- O script utiliza `max_workers = os.cpu_count() - 1` para paralelizar as requisições
- Logs de cada ação são organizados individualmente
- Erros são tratados e exibidos de forma clara

---

## 📋 Autor

**Mateus**  
Desenvolvido como parte do projeto de TCC 🎓  
