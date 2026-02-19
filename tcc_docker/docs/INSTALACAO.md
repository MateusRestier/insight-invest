# 🚀 Guia de Instalação - INSIGHT-INVEST

## Pré-requisitos

### Obrigatórios
- **Docker Desktop** (Windows/Mac) ou **Docker Engine** (Linux)
- **docker-compose** (geralmente já vem com Docker Desktop)
- **Git** (para clonar o repositório)

### Opcionais (para desenvolvimento local sem Docker)
- **Python 3.12**
- **PostgreSQL 15**
- **DBeaver** ou outro cliente SQL (para visualizar o banco)

---

## Instalação com Docker (Recomendado)

### 1️⃣ Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/insight-invest.git
cd insight-invest/tcc_docker
```

### 2️⃣ Subir o Banco de Dados

```bash
docker compose up -d db
```

**Verificar se está rodando:**
```bash
docker compose ps
```

Deve mostrar:
```
NAME                STATUS
tcc_docker-db-1     Up
```

### 3️⃣ Restaurar um Backup (Opcional)

Se você tem um arquivo de backup:

```bash
python app/backup.py
# Escolha opção 2 (Restaurar)
# Selecione o arquivo .dump
```

### 4️⃣ Construir a Imagem da Aplicação

```bash
docker compose build scraper
```

### 5️⃣ Subir a Aplicação

```bash
docker compose up -d scraper
```

### 6️⃣ Executar o Scraper (Primeira Coleta)

```bash
docker compose exec scraper python scraper_indicadores.py
```

Aguarde ~1-2 minutos. Você verá mensagens como:
```
✅ PETR4 coletado e salvo.
✅ VALE3 coletado e salvo.
...
```

### 7️⃣ Treinar o Classificador

```bash
docker compose exec scraper python classificador.py
```

Aguarde ~5-10 minutos. Você verá:
- Carregamento de dados
- Remoção de duplicatas
- Cálculo de features
- Validação cruzada temporal
- Métricas finais (Acurácia, ROC-AUC)

### 8️⃣ Gerar Previsões de Preços

```bash
docker compose exec scraper python regressor_preco.py
```

### 9️⃣ Gerar Recomendações

```bash
docker compose exec scraper python recomendador_acoes.py
```

### 🔟 Acessar o Dashboard

```bash
docker compose exec scraper python dashboard/app.py
```

Abra o navegador em: **http://localhost:8050**

---

## Instalação Local (Sem Docker)

### 1️⃣ Instalar PostgreSQL

**Windows:**
- Baixe de: https://www.postgresql.org/download/windows/
- Instale com as credenciais padrão:
  - Usuário: `postgres`
  - Senha: `password`
  - Porta: `5432`

**Linux:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**Mac:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

### 2️⃣ Criar Banco de Dados

```bash
psql -U postgres
```

```sql
CREATE DATABASE stocks;
CREATE USER user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE stocks TO user;
\q
```

### 3️⃣ Instalar Python 3.12

**Windows:**
- Baixe de: https://www.python.org/downloads/
- Marque "Add Python to PATH"

**Linux:**
```bash
sudo apt install python3.12 python3.12-venv
```

**Mac:**
```bash
brew install python@3.12
```

### 4️⃣ Criar Ambiente Virtual

```bash
cd insight-invest/tcc_docker
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 5️⃣ Instalar Dependências

```bash
pip install -r requirements.txt
```

**Nota:** Se estiver no Windows, remova as linhas `pywin32` e `pyodbc` do requirements.txt antes.

### 6️⃣ Configurar Variáveis de Ambiente

**Windows (PowerShell):**
```powershell
$env:DB_HOST="localhost"
$env:DB_NAME="stocks"
$env:DB_USER="user"
$env:DB_PASS="password"
$env:DB_PORT="5432"
```

**Linux/Mac:**
```bash
export DB_HOST=localhost
export DB_NAME=stocks
export DB_USER=user
export DB_PASS=password
export DB_PORT=5432
```

### 7️⃣ Executar Componentes

```bash
# 1. Coletar dados
python app/scraper_indicadores.py

# 2. Treinar classificador
python app/classificador.py

# 3. Gerar previsões
python app/regressor_preco.py

# 4. Gerar recomendações
python app/recomendador_acoes.py

# 5. Iniciar dashboard
python app/dashboard/app.py
```

---

## Conectar no DBeaver

### Configuração da Conexão

1. **Nova Conexão** → Selecione **PostgreSQL**

2. **Aba "Main":**
   - **Host:** `localhost`
   - **Port:** `5432`
   - **Database:** `stocks`
   - **Username:** `user`
   - **Password:** `password`
   - ✅ Marque "Save password"

3. **Test Connection** → Deve conectar!

### Explorar Tabelas

```sql
-- Ver todas as ações coletadas
SELECT DISTINCT acao FROM indicadores_fundamentalistas
ORDER BY acao;

-- Ver indicadores mais recentes de PETR4
SELECT * FROM indicadores_fundamentalistas
WHERE acao = 'PETR4'
ORDER BY data_coleta DESC
LIMIT 10;

-- Ver previsões de preços
SELECT * FROM resultados_precos
WHERE acao = 'PETR4'
ORDER BY data_previsao;

-- Ver recomendações
SELECT * FROM recomendacoes_acoes
ORDER BY data_insercao DESC
LIMIT 20;
```

---

## Orquestração Diária (Opcional)

Para executar tarefas automaticamente todos os dias às 01:00:

### Com Docker

```bash
docker compose exec scraper python executar_tarefas_diarias.py
```

**Deixa rodando em background:**
```bash
docker compose exec -d scraper python executar_tarefas_diarias.py
```

### Sem Docker

**Windows (Task Scheduler):**
1. Abra "Task Scheduler"
2. Create Task → Nome: "INSIGHT-INVEST Daily"
3. Trigger: Daily at 01:00
4. Action: Start a program
   - Program: `python`
   - Arguments: `app/executar_tarefas_diarias.py`
   - Start in: `d:\caminho\para\tcc_docker`

**Linux (cron):**
```bash
crontab -e
```

Adicione:
```cron
0 1 * * * cd /caminho/para/tcc_docker && python app/executar_tarefas_diarias.py >> logs/daily.log 2>&1
```

---

## Troubleshooting

### Erro: "No module named 'psycopg2'"

```bash
pip install psycopg2-binary==2.9.10
```

### Erro: "pywin32 not found" no Docker

Remova a linha `pywin32==306` do `requirements.txt`

### Erro: "Connection refused" no PostgreSQL

```bash
# Verificar se está rodando
docker compose ps

# Reiniciar banco
docker compose restart db
```

### Dashboard não abre em localhost:8050

```bash
# Verificar se porta está em uso
netstat -ano | findstr :8050

# Matar processo (Windows - substitua PID)
taskkill /PID <PID> /F

# Matar processo (Linux/Mac)
kill -9 $(lsof -t -i:8050)
```

### Scraper muito lento

- **Solução:** O scraper usa ThreadPoolExecutor com `cpu_count() - 1` threads
- Verifique sua conexão de internet
- Alguns tickers podem estar fora do ar no Investidor10

---

## Próximos Passos

Após a instalação bem-sucedida:

1. ✅ Explore o dashboard: http://localhost:8050
2. ✅ Teste uma recomendação pontual (aba "Recomendador")
3. ✅ Faça uma previsão multi-dia (aba "Previsões")
4. ✅ Conecte no DBeaver e explore os dados
5. ✅ Leia a documentação em `docs/ARQUITETURA.md`

---

## Comandos Úteis

```bash
# Ver logs do container
docker compose logs -f scraper

# Entrar no container
docker compose exec scraper bash

# Parar tudo
docker compose down

# Parar e remover volumes (CUIDADO: apaga o banco!)
docker compose down -v

# Rebuild forçado
docker compose build --no-cache
```