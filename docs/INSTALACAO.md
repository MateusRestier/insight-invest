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
git clone https://github.com/MateusRestier/insight-invest.git
cd insight-invest/insight
```

### 2️⃣ Criar o arquivo de variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com os valores desejados (para uso local, os valores padrão já funcionam):

```env
POSTGRES_DB=stocks
POSTGRES_USER=user
POSTGRES_PASSWORD=password
```

### 3️⃣ Subir os containers

```bash
docker compose up --build
```

Isso sobe automaticamente 3 containers:
- **db** → PostgreSQL (banco de dados)
- **dashboard** → Interface web em http://localhost:8050
- **scheduler** → Orquestrador de tarefas diárias (roda às 01:00)

**Verificar se está tudo rodando:**
```bash
docker compose ps
```

Deve mostrar:
```
NAME                   STATUS
insight-db-1           Up (healthy)
insight-dashboard-1    Up
insight-scheduler-1    Up
```

### 4️⃣ Restaurar um Backup (Opcional)

Se você tem um arquivo `.dump`, restaure antes de subir os outros containers:

```bash
# Suba só o banco primeiro
docker compose up -d db

# Restaure o backup
python app/backup.py
# Escolha opção 2 (Restaurar) e selecione o arquivo

# Suba o restante
docker compose up -d dashboard scheduler
```

### 5️⃣ Executar o Scraper (Primeira Coleta)

```bash
docker compose exec dashboard python scraper_indicadores.py
```

Aguarde ~1-2 minutos. Você verá mensagens como:
```
✅ PETR4 coletado e salvo.
✅ VALE3 coletado e salvo.
...
```

### 6️⃣ Treinar o Classificador

```bash
docker compose exec dashboard python classificador.py
```

Aguarde ~5-10 minutos. Você verá:
- Carregamento de dados
- Remoção de duplicatas
- Cálculo de features
- Validação cruzada temporal
- Métricas finais (Acurácia, ROC-AUC)

### 7️⃣ Gerar Previsões de Preços

```bash
docker compose exec dashboard python regressor_preco.py
```

### 8️⃣ Gerar Recomendações

```bash
docker compose exec dashboard python recomendador_acoes.py
```

### 9️⃣ Acessar o Dashboard

Abra o navegador em: **http://localhost:8050**

O dashboard já está rodando desde o passo 3 — não precisa executar nada adicional.

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
CREATE USER "user" WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE stocks TO "user";
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
cd insight-invest/insight
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

-- Ver recomendações (mais recentes por ação)
SELECT * FROM recomendacoes_acoes
ORDER BY data_recomendacao DESC, acao
LIMIT 20;
```

---

## Orquestração Diária

O container `scheduler` já cuida da execução automática diária às 01:00 enquanto estiver rodando. Basta manter os containers no ar:

```bash
docker compose up -d
```

Para verificar quando foi a última execução:
```bash
docker compose logs scheduler
```

### Sem Docker (Linux - cron)

```bash
crontab -e
```

Adicione:
```cron
0 1 * * * cd /caminho/para/insight && python app/executar_tarefas_diarias.py >> logs/daily.log 2>&1
```

---

## Troubleshooting

### Erro: "No module named 'psycopg2'"

```bash
pip install psycopg2-binary==2.9.10
```

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
# Ver logs em tempo real
docker compose logs -f dashboard
docker compose logs -f scheduler

# Entrar no container
docker compose exec dashboard bash

# Parar tudo
docker compose down

# Parar e remover volumes (CUIDADO: apaga o banco!)
docker compose down -v

# Rebuild forçado
docker compose build --no-cache
```
