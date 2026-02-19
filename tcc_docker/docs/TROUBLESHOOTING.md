# 🛟 Troubleshooting - Soluções de Problemas Comuns

## 🐳 Problemas com Docker

### ❌ Erro: "pywin32 not found" ao fazer build

**Sintoma:**
```
ERROR: No matching distribution found for pywin32
```

**Causa:** `pywin32` é uma biblioteca específica do Windows e não funciona em containers Linux.

**Solução:**
```bash
# Edite requirements.txt e remova as linhas:
# pywin32==306
# pyodbc==5.1.0

# Rebuild
docker compose build --no-cache
```

---

### ❌ Erro: "EvalSymlinks: too many links" no docker cp

**Sintoma:**
```
EvalSymlinks: too many links
Command '['docker', 'cp', 'd:\\Google Drive\\...', '...']' returned non-zero exit status 1
```

**Causa:** Docker tem problemas com:
1. Caminhos com espaços ("Google Drive")
2. Destinos com links simbólicos (`/var/lib/postgresql/data/`)

**Solução:** Use stdin/stdout no backup (já corrigido em `app/backup.py`):
```python
# Em vez de docker cp, use:
with open(arquivo, 'rb') as f:
    subprocess.run([
        "docker", "exec", "-i", CONTAINER_NAME,
        "pg_restore", "-U", DB_USER, "-d", DB_NAME,
        "--clean", "--if-exists"
    ], stdin=f, check=True)
```

---

### ❌ Container não sobe

**Sintoma:**
```bash
docker compose up -d
# Mostra "Exited (1)" ou não aparece
```

**Diagnóstico:**
```bash
# Ver status
docker compose ps

# Ver logs
docker compose logs db
docker compose logs scraper
```

**Soluções:**

1. **Porta 5432 ocupada:**
```bash
# Windows
netstat -ano | findstr :5432
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :5432
kill -9 <PID>
```

2. **Volume corrompido:**
```bash
docker compose down -v  # CUIDADO: apaga dados!
docker compose up -d
```

3. **Rebuild completo:**
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

### ❌ Erro: "no such service" ao executar comandos

**Sintoma:**
```bash
docker compose exec scraper python app.py
# Error: no such service: scraper
```

**Causa:** Container não está rodando ou nome está errado.

**Solução:**
```bash
# Verificar nome correto
docker compose ps

# Se não aparecer, subir
docker compose up -d scraper

# Usar nome correto (pode ser "app" ou "scraper")
docker compose exec <nome-correto> python app.py
```

---

## 🗄️ Problemas com PostgreSQL

### ❌ Erro: "Connection refused" ao conectar

**Sintoma:**
```
psycopg2.OperationalError: connection to server at "localhost", port 5432 failed: Connection refused
```

**Diagnóstico:**
```bash
# Verificar se container está rodando
docker compose ps

# Ver logs do banco
docker compose logs db
```

**Soluções:**

1. **Banco não está rodando:**
```bash
docker compose up -d db
```

2. **Porta errada nas variáveis de ambiente:**
```bash
# Verificar em docker-compose.yml:
ports:
  - "5432:5432"  # Host:Container

# Se a porta do host for diferente, ajuste DB_PORT
export DB_PORT=5433  # ou outra porta
```

3. **Firewall bloqueando:**
```bash
# Windows - permitir porta 5432
netsh advfirewall firewall add rule name="PostgreSQL" dir=in action=allow protocol=TCP localport=5432

# Linux
sudo ufw allow 5432/tcp
```

---

### ❌ Erro: "password authentication failed"

**Sintoma:**
```
psycopg2.OperationalError: FATAL: password authentication failed for user "user"
```

**Solução:**
```bash
# Verificar credenciais em docker-compose.yml
services:
  db:
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: stocks

# Garantir que variáveis de ambiente estão corretas
export DB_USER=user
export DB_PASS=password
```

---

### ❌ Tabelas não existem

**Sintoma:**
```
psycopg2.errors.UndefinedTable: relation "indicadores_fundamentalistas" does not exist
```

**Causa:** Banco criado mas tabelas não foram criadas.

**Solução:**

**Opção 1: Restaurar backup**
```bash
python app/backup.py
# Escolha opção 2 e selecione um .dump
```

**Opção 2: Criar tabelas manualmente**
```sql
-- Conecte via DBeaver ou psql e execute:

CREATE TABLE IF NOT EXISTS public.indicadores_fundamentalistas (
  acao TEXT NOT NULL,
  data_coleta DATE NOT NULL,
  cotacao NUMERIC,
  pl NUMERIC,
  pvp NUMERIC,
  roe NUMERIC,
  dividend_yield NUMERIC,
  margem_liquida NUMERIC,
  div_liq_patrimonio NUMERIC,
  lpa NUMERIC,
  vpa NUMERIC,
  variacao_12m NUMERIC,
  psr NUMERIC,
  payout NUMERIC,
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
  giro_ativos NUMERIC,
  roic NUMERIC,
  roa NUMERIC,
  div_liq_ebitda NUMERIC,
  div_liq_ebit NUMERIC,
  div_bruta_patrimonio NUMERIC,
  patrimonio_ativos NUMERIC,
  passivos_ativos NUMERIC,
  liquidez_corrente NUMERIC,
  PRIMARY KEY (acao, data_coleta)
);

CREATE TABLE IF NOT EXISTS public.resultados_precos (
  acao TEXT NOT NULL,
  data_previsao DATE NOT NULL,
  preco_previsto NUMERIC NOT NULL,
  data_calculo DATE NOT NULL,
  data_calculo TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (acao, data_previsao)
);

CREATE TABLE IF NOT EXISTS public.recomendacoes_acoes (
  acao TEXT NOT NULL,
  recomendada NUMERIC NOT NULL,
  nao_recomendada NUMERIC NOT NULL,
  resultado TEXT NOT NULL,
  data_insercao TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Opção 3: Executar scraper (cria dados)**
```bash
docker compose exec scraper python scraper_indicadores.py
```

---

## 🌐 Problemas com Web Scraping

### ❌ Erro: "Connection timeout" ao fazer scraping

**Sintoma:**
```
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='investidor10.com.br', ...): Max retries exceeded
```

**Causas possíveis:**
1. Sem conexão com internet
2. Site fora do ar
3. Bloqueio de bot

**Soluções:**

1. **Verificar conexão:**
```bash
ping investidor10.com.br
```

2. **Aumentar timeout:**
```python
# Em scraper_indicadores.py
response = requests.get(url, headers=headers, timeout=30)  # Era 10
```

3. **Delay entre requisições:**
```python
import time
time.sleep(1)  # 1 segundo entre cada ticker
```

---

### ❌ Scraper não encontra indicadores

**Sintoma:**
```
⚠️ PETR4 - Indicador P/L não encontrado
```

**Causas:**
1. HTML do site mudou
2. Ação não tem o indicador
3. Seletor CSS incorreto

**Diagnóstico:**
```python
# Adicione prints para debug
print(f"HTML: {soup.prettify()[:500]}")
```

**Solução:**
1. Verifique manualmente no site se o indicador existe
2. Use DevTools do browser para inspecionar HTML
3. Ajuste seletores em `get_valor_indicador()`

---

## 🤖 Problemas com Machine Learning

### ❌ Erro: "No module named 'sklearn'"

**Sintoma:**
```
ModuleNotFoundError: No module named 'sklearn'
```

**Solução:**
```bash
pip install scikit-learn==1.6.1
```

---

### ❌ Modelo não encontrado

**Sintoma:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'modelo/modelo_classificador_desempenho.pkl'
```

**Causa:** Modelo não foi treinado ainda.

**Solução:**
```bash
# Treinar modelo
docker compose exec scraper python classificador.py

# Verificar se foi criado
ls -la app/modelo/
```

---

### ❌ Métricas ruins (Acurácia < 50%)

**Possíveis causas:**
1. Dados insuficientes
2. Data leakage
3. Features ruins

**Diagnóstico:**
```python
# Adicione prints no classificador.py
print(f"Tamanho treino: {len(X_train)}")
print(f"Tamanho teste: {len(X_hold)}")
print(f"Balanceamento: {y_train.value_counts()}")
```

**Soluções:**
1. Colete mais dados (execute scraper por mais dias)
2. Verifique se hold-out é temporal (não aleatório)
3. Analise feature importances

---

## 📊 Problemas com Dashboard

### ❌ Dashboard não abre em localhost:8050

**Sintoma:**
```bash
# Browser mostra "This site can't be reached"
```

**Diagnóstico:**
```bash
# Verificar se porta está ocupada
netstat -ano | findstr :8050

# Verificar se processo está rodando
docker compose ps
# ou
ps aux | grep "python dashboard/app.py"
```

**Soluções:**

1. **Porta ocupada:**
```bash
# Windows
taskkill /PID <PID> /F

# Linux/Mac
kill -9 <PID>
```

2. **Mudar porta:**
```python
# Em app/dashboard/app.py
if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8051)  # Era 8050
```

3. **Firewall bloqueando:**
```bash
# Windows - permitir porta 8050
netsh advfirewall firewall add rule name="Dash" dir=in action=allow protocol=TCP localport=8050
```

---

### ❌ Gráficos não carregam / Página em branco

**Sintoma:**
```
Dashboard abre mas gráficos não aparecem
```

**Diagnóstico:**
```bash
# Ver logs do dashboard
docker compose logs scraper

# Ver console do browser (F12)
```

**Soluções:**

1. **Dados não existem:**
```sql
-- Conecte no DBeaver e verifique
SELECT COUNT(*) FROM indicadores_fundamentalistas;
SELECT COUNT(*) FROM resultados_precos;
SELECT COUNT(*) FROM recomendacoes_acoes;
```

2. **Erro de SQL:**
```python
# Adicione try/except nos callbacks
try:
    df = pd.read_sql(query, conn)
except Exception as e:
    print(f"Erro SQL: {e}")
    return dash.no_update
```

---

### ❌ Previsão sob demanda trava

**Sintoma:**
```
Barra de progresso fica em 0% para sempre
```

**Causa:** Thread de cálculo travou ou arquivo de status não existe.

**Diagnóstico:**
```bash
# Verificar arquivos de cache
ls -la app/dashboard/cache_status/
ls -la app/dashboard/cache_results/
```

**Solução:**
```bash
# Limpar cache
rm -rf app/dashboard/cache_status/*
rm -rf app/dashboard/cache_results/*

# Tentar novamente
```

---

## 🔧 Problemas de Desenvolvimento

### ❌ Mudanças no código não refletem

**Sintoma:**
```
Editei o código mas comportamento é o mesmo
```

**Causas:**
1. Container não sincronizado
2. Cache do Python (.pyc)
3. Modelo antigo (.pkl)

**Soluções:**

1. **Rebuild container:**
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

2. **Limpar cache Python:**
```bash
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

3. **Re-treinar modelo:**
```bash
rm app/modelo/*.pkl
docker compose exec scraper python classificador.py
```

---

### ❌ Import Error: circular import

**Sintoma:**
```
ImportError: cannot import name 'X' from partially initialized module 'Y' (most likely due to a circular import)
```

**Causa:** Arquivo A importa B, e B importa A.

**Solução:**
1. Reorganize imports
2. Use `import` local (dentro de função)
3. Refatore para remover dependência circular

---

## 📧 Problemas com Email (Backup)

### ❌ Erro: "Outlook not found"

**Sintoma:**
```
❌ Erro ao enviar email: Outlook not found
```

**Causa:** Sistema não tem Outlook instalado ou não está configurado.

**Solução:**

**Opção 1:** Comentar função de email
```python
# Em backup.py
def criar_backup():
    # ... código do backup ...

    # enviar_email_com_anexo(dump_local)  # Comentar
```

**Opção 2:** Usar SMTP em vez de Outlook
```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def enviar_email_smtp(caminho_anexo):
    msg = MIMEMultipart()
    msg['From'] = "seu-email@gmail.com"
    msg['To'] = "destino@gmail.com"
    msg['Subject'] = f"Backup - {datetime.now()}"

    with open(caminho_anexo, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={caminho_anexo.name}')
        msg.attach(part)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login("seu-email@gmail.com", "sua-senha-app")
    server.send_message(msg)
    server.quit()
```

---

## 🔍 Debug Geral

### Como ativar modo debug?

```python
# Em qualquer script .py, adicione no início:
import logging
logging.basicConfig(level=logging.DEBUG)

# Ou adicione prints estratégicos
print(f"DEBUG: variavel = {variavel}")
```

### Como ver queries SQL executadas?

```python
# Em db_connection.py ou nos scripts
import psycopg2.extras
psycopg2.extras.register_default_jsonb(conn_or_curs=cur, globally=True)

# Adicione antes de executar query
print(f"SQL: {query}")
cur.execute(query)
```

### Como testar componente isoladamente?

```python
# Exemplo: testar só o scraper de uma ação
if __name__ == "__main__":
    resultado = coletar_indicadores("PETR4")
    print(resultado)
```

---

## 📝 Logs e Debugging

### Ver logs do Docker

```bash
# Logs em tempo real
docker compose logs -f scraper

# Últimas 100 linhas
docker compose logs --tail=100 scraper

# Logs do banco
docker compose logs db
```

### Criar arquivo de log

```python
# Adicione no início dos scripts
import logging

logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("Iniciando processo...")
```

---

## 🆘 Ainda com Problemas?

Se nenhuma solução acima funcionou:

1. ✅ Verifique versões:
```bash
python --version  # Deve ser 3.12
docker --version
docker compose --version
```

2. ✅ Limpe tudo e recomece:
```bash
docker compose down -v
rm -rf app/modelo/*.pkl
rm -rf app/dashboard/cache_*/*
docker compose build --no-cache
docker compose up -d
```

3. ✅ Verifique issues similares no GitHub (se público)

4. ✅ Consulte documentação oficial:
- [Docker Docs](https://docs.docker.com/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Dash Docs](https://dash.plotly.com/)
- [scikit-learn Docs](https://scikit-learn.org/)

---

**Última atualização:** 2025-02-19