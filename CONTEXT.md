# CONTEXT.md

## O que é este arquivo

Este arquivo é o **diário de bordo de IAs** do projeto. Ele não descreve o projeto em si (isso é papel do README), mas sim **o que cada IA fez, decidiu e deixou pendente** — para que a próxima IA ou sessão possa continuar exatamente de onde parou, sem precisar reler todo o código.

## Como usar

**Ao iniciar uma sessão:**
> "Leia o CONTEXT.md e continue dali."

A IA deve ler o arquivo inteiro, absorver o contexto e agir como continuação da sessão anterior.

**Ao encerrar uma sessão:**
> "Atualize o CONTEXT.md com o que foi feito."

A IA deve adicionar uma nova entrada na seção **Histórico**, seguindo o formato estabelecido abaixo.

## Regras

1. **Nunca apague entradas antigas.** Apenas adicione novas no topo do Histórico.
2. **Cada entrada = uma sessão de trabalho.** Se a mesma IA fez várias coisas em sequência, agrupe tudo em uma única entrada.
3. **Seja específica, não genérica.** Não escreva "corrigi bugs". Escreva qual bug, qual arquivo, qual foi a causa e qual foi o fix.
4. **Documente decisões arquiteturais.** Se você escolheu uma abordagem em vez de outra, explique o porquê.
5. **Sinalize pendências.** Se deixou algo incompleto ou identificou algo a fazer, registre em "Pendências" dentro da entrada.
6. **Assine a entrada** com o modelo e ferramenta usada (ex: `Claude Sonnet 4.5 via Cursor`).

## Formato de uma entrada

```
---
### [vX.Y] Título curto descrevendo o escopo da sessão
**Data:** YYYY-MM-DD  
**IA:** <modelo> via <ferramenta>

#### O que foi feito
- ...

#### Decisões e motivos
- ...

#### Pendências / próximos passos
- ...
---
```

O número de versão `vX.Y` é incremental — `X` muda quando há uma mudança estrutural grande (arquitetura, migração), `Y` muda para adições ou correções menores.

---

## Histórico

---
### [v2.8] Fix KeyError 'acao' no regressor
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`src/models/regressor_preco.py`**:
  - após `groupby('acao').apply(...)`, garantir `acao` como coluna:
    - se `acao` virar nível índice (`MultiIndex` ou índice simples), aplicar `reset_index`.
  - em `preparar_dados_regressao()`, adicionar checagem defensiva:
    - tentar recuperar `acao` do índice;
    - lançar `KeyError` explícito se coluna continuar ausente.

#### Decisões e motivos

- Logs Railway após disparo de `/tarefas/treinar` mostraram novo erro:
  - `KeyError: 'acao'` em `acoes = df.loc[X.index, 'acao']`.
- Em alguns cenários de pandas, `groupby/apply` altera estrutura e remove `acao` de `columns`.
- Tratamento explícito torna pipeline estável entre ambientes/versões.

#### Pendências / próximos passos

- Rodar `Treinar Modelos` no GitHub Actions novamente.
- Validar que erro `KeyError: 'acao'` não reaparece.
- Confirmar atualização de previsões na aba **Prever preço**.

---
### [v2.7] Fix MergeError no treino regressor
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`src/models/regressor_preco.py`**:
  - em `adicionar_preco_futuro()`, padronizado dtype das chaves de data usadas no `pd.merge_asof`:
    - `left['data_futura_alvo']` convertido para `datetime64[ns]`;
    - `right['data_coleta']` convertido para `datetime64[ns]`.
  - `left` e `right` passaram a usar `.copy()` e ordenação explícita por suas colunas de data.

#### Decisões e motivos

- Logs Railway mostraram falha em background task de treino:
  - `pandas.errors.MergeError: incompatible merge keys [0] dtype('<M8[us]') and dtype('<M8[s]')`.
- `merge_asof` exige dtypes idênticos nas chaves; normalização explícita remove variação de precisão temporal entre datasets.

#### Pendências / próximos passos

- Rodar GitHub Action `Treinar Modelos` novamente.
- Confirmar ausência de novo stacktrace `MergeError` em logs Railway.
- Validar aba **Prever preço** após treino concluir.

---
### [v2.5] Hardening de deploy Railway (healthcheck e fechamento de pendências)
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`railway.json`**:
  - adicionado `healthcheckPath: "/health"` para o Railway validar serviço pelo endpoint correto.
- **Validação de estado da migração**:
  - confirmado que o repositório já estava consistente com modelo de serviço único (API + Dash no mesmo processo).

#### Decisões e motivos

- Healthcheck explícito reduz risco de falso negativo em boot/deploy e facilita diagnóstico no painel Railway.

#### Pendências / próximos passos

- No painel Railway:
  - manter apenas um serviço de aplicação;
  - confirmar variáveis `DB_*` e `API_KEY`;
  - redeploy e teste de `GET /health` e `/`.
- Se necessário, restaurar dump no PostgreSQL Railway:
  - `python scripts/backup.py --restaurar --arquivo backups/backup_2025-11-10_18-37-02.dump`
  - `python scripts/validar_restore.py`

---
### [v2.4] Migração para Railway (serviço único + dump local)
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **Unificação de runtime HTTP**:
  - `src/api/main.py` passou a montar o dashboard Dash no FastAPI via `WSGIMiddleware`.
  - Resultado: API + Dashboard no mesmo processo/serviço (modelo local compartilhado).
- **Recomendador preparado para serviço único**:
  - `src/dashboard/pages/recomendador.py` ganhou fallback de URL interna (`http://127.0.0.1:$PORT`) quando `API_URL` não estiver definida.
  - `API_KEY` permanece obrigatório.
- **Configuração Railway**:
  - criado `railway.json` com start command único: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`.
- **Ambiente/documentação**:
  - `.env.example` atualizado para PostgreSQL Railway e `API_URL` opcional.
  - `README.md` atualizado com fluxo Railway, execução unificada, restore por dump e validação pós-restore.
- **Backup/restore operacional**:
  - `scripts/backup.py` recebeu flags de CLI:
    - `--criar`
    - `--restaurar`
    - `--arquivo`
  - novo script `scripts/validar_restore.py` para contagem das tabelas após restore.
- **Render removido**:
  - `render.yaml` removido.
  - `.python-version` removido por decisão do usuário (contexto Render).
- **Workflows**:
  - `.github/workflows/{coletar,treinar,recomendar}.yml` mantidos e ajustados para contexto Railway (mesmo contrato de `API_URL` + `API_KEY` via secrets).

#### Decisões e motivos

- Serviço único elimina problema de filesystem isolado entre serviços (erro recorrente de `.pkl` ausente no dashboard).
- Reuso do dump versionado (`backups/backup_2025-11-10_18-37-02.dump`) simplifica migração e evita depender do Supabase.

#### Pendências / próximos passos

- No Railway:
  - criar serviço app + plugin PostgreSQL;
  - configurar vars `DB_*` e `API_KEY`;
  - deploy e validação de `GET /health`, dashboard `/`, e endpoints `/tarefas/*`.
- Restaurar dump no banco Railway:
  - `python scripts/backup.py --restaurar --arquivo backups/backup_2025-11-10_18-37-02.dump`
  - `python scripts/validar_restore.py`
- Atualizar GitHub Secrets `API_URL` para URL Railway da API unificada.

---
### [v2.3] Recomendador via API (sem depender de arquivo local no dashboard)
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`src/api/main.py`**:
  - fix em `_run_treinar`: `treinar_modelo` (inexistente) → `executar_pipeline_classificador`.
  - novo endpoint síncrono `POST /recomendacao/{ticker}` (auth via `X-API-Key`) que:
    - coleta dados (`coletar_indicadores`);
    - calcula feature de Graham;
    - carrega modelo (`modelo/modelo_classificador_desempenho.pkl`);
    - retorna JSON com `ticker`, `resultado` e probabilidades.
- **`src/dashboard/pages/recomendador.py`**:
  - removida dependência direta de `recomendar_acao` local.
  - callback do botão **Recomendar** agora chama a API via `requests.post` usando `API_URL` + `API_KEY`.
  - mensagens de erro explícitas para ausência de env vars, falha de rede ou erro HTTP da API.
- **`render.yaml`**:
  - serviço `insight-invest-dashboard` recebeu env vars `API_URL` e `API_KEY` (ambas `sync: false`).
- **`.env.example`**:
  - adicionada variável `API_URL` com exemplo da URL do serviço API no Render.

#### Decisões e motivos

- **Motivo principal:** no Render free, API e dashboard rodam em serviços com filesystem isolado.  
  Treinar na API não garante presença do `.pkl` no dashboard.
- **Decisão:** dashboard virou cliente da API para recomendação pontual; modelo fica centralizado no serviço API.

#### Pendências / próximos passos

- Configurar no Render (serviço dashboard):
  - `API_URL=https://insight-invest-api.onrender.com`
  - `API_KEY=<mesmo valor do serviço API>`
- Fazer deploy das mudanças e validar:
  1. `POST /tarefas/treinar` sem `ImportError`;
  2. botão **Recomendar** consumindo `POST /recomendacao/{ticker}`.
- Investigar separadamente a aba **Prever Preço** (relato de clique sem resposta), pois não foi alterada nesta sessão.

---
### [v2.2] FastAPI + deploy Render + GitHub Actions crons
**Data:** 2026-04-14
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

- **`src/api/__init__.py`**: criado (vazio)
- **`src/api/main.py`**: FastAPI com 5 endpoints:
  - `GET /health` — sem auth, para UptimeRobot
  - `GET /tarefas/status` — retorna tarefa em andamento
  - `POST /tarefas/coletar` — 202, roda `scraper_orquestrador.main()` em background thread
  - `POST /tarefas/treinar` — 202, roda classificador + regressor em background
  - `POST /tarefas/recomendar` — 202, roda `recomendar_varias_acoes` em background
  - Auth via `X-API-Key` header; retorna 409 se outra tarefa já estiver rodando
- **`render.yaml`**: 2 web services com runtime Docker (`insight-invest-api` porta via `$PORT`, `insight-invest-dashboard` idem)
- **`.github/workflows/coletar.yml`**: 2 crons dias úteis (21:00 e 23:00 UTC = 18:00 e 20:00 BRT, após fechamento do pregão), retry automático com 5 tentativas / 2 min de espera, 409 aborta silenciosamente
- **`.github/workflows/treinar.yml`**: 04:00 UTC, mesmo padrão de retry
- **`.github/workflows/recomendar.yml`**: 08:00 UTC, mesmo padrão de retry
- **`requirements.txt`**: adicionado `fastapi==0.115.12`, `uvicorn==0.34.0`
- **`src/dashboard/app.py`**: porta via `int(os.getenv("PORT", 8050))` para compatibilidade com Render
- **`src/data/scraper_orquestrador.py`**: removido import morto `ThreadPoolExecutor`

#### Decisões e motivos

- **202 Accepted + BackgroundTasks**: Render free tier mata requests após 30s; tarefas longas (coleta de 148 tickers) precisam rodar em background. O caller (GitHub Actions) só precisa confirmar que o disparo foi aceito.
- **Mutex global `_tarefa_em_andamento`**: evita execuções paralelas acidentais; 409 é retornado se já houver tarefa rodando. O orquestrador já é sequencial, então não há risco de race condition interna.
- **Crons após fechamento do pregão**: cotação e indicadores derivados (P/L, P/VP etc.) ficam estáveis após 17:55 BRT. Coletar durante o pregão capturaria preços mid-day, menos representativos para análise fundamentalista.
- **Orquestrador sequencial**: já era assim antes; confirmado que não usa ThreadPoolExecutor (import foi removido). Scrapers individuais mantêm paralelismo quando rodados standalone.
- **`sync: false` no render.yaml**: variáveis sensíveis (DB_PASS, API_KEY) não são commitadas; preenchidas manualmente no painel do Render.

#### Fixes de deploy (após v2.2)

- **`.python-version`** + `PYTHON_VERSION=3.12.0` no `render.yaml`: Render usava Python 3.14 por padrão — `pandas==2.2.2` não tem wheel para 3.14 e falha na compilação
- **`requests==2.32.3` → `>=2.32.4`**: `fundamentus==0.3.2` exige `requests>=2.32.4`
- **`pandas==2.2.2` → `>=2.3.0`** e **`numpy==2.1.0` → `>=2.1.0`**: `fundamentus==0.3.2` exige `pandas>=2.3.0`; pip resolveu para pandas 3.0.2 e numpy 2.4.4
- **`src/dashboard/pages/recomendador.py`**: importava `scraper_indicadores` (nome antigo) — corrigido para `scraper_orquestrador.coletar_com_fallback`
- **`render.yaml` `plan: free`**: Render criava instâncias Starter ($7/mês) por padrão
- **`render.yaml` `runtime: docker` → `env: python`**: Docker runtime não aceita `startCommand` no Blueprint

#### Pendências / próximos passos

- Adicionar GitHub Secrets: `API_URL` e `API_KEY`
- Configurar UptimeRobot para pingar `GET /health` a cada 5 min (evitar sleep do free tier)

---
### [v2.1] Migração banco de dados local → Supabase
**Data:** 2026-04-14
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

- **Supabase** criado em `insight-invest` (região Oregon, free tier)
- DDL das 3 tabelas executado no SQL Editor do Supabase
- **`src/core/db_connection.py`**: adicionado `python-dotenv` para carregar `.env`
  automaticamente — sem isso, fora do Docker o código usava o banco local
- **`docker-compose.yml`**: removido `DB_HOST: db` hardcoded nos containers
  `dashboard` e `scheduler`; ambos passam a usar `env_file: .env`; serviço `db`
  (postgres local) movido para profile `local` — só sobe com
  `docker compose --profile local up`
- **`.env.example`**: variáveis `POSTGRES_*` substituídas por `DB_*` com formato
  Supabase (Session Pooler)
- **`scripts/backup.py`**: adicionado `python-dotenv`, função `_find_pg_tool` para
  localizar `pg_dump`/`pg_restore` sem PATH configurado (Windows), flags
  `--no-owner --no-privileges` para compatibilidade com Supabase, emojis removidos
- **`requirements.txt`**: adicionado `python-dotenv==1.0.1`
- Backup local `backup_2025-11-10_18-37-02.dump` restaurado com sucesso no Supabase

#### Decisões e motivos

- **Session Pooler (porta 5432)** em vez de Direct Connection: Render usa IPv4,
  a conexão direta do Supabase é IPv6. Transaction Pooler (6543) foi descartado
  por incompatibilidade com prepared statements do psycopg2.
- **`env_file: .env`** no docker-compose em vez de listar variáveis individualmente:
  evita divergência entre `.env` e `docker-compose.yml` a cada nova variável.
- **Profile `local`** para o container postgres: mantém opção de dev local sem
  afetar o fluxo principal que agora usa Supabase.

#### Pendências / próximos passos
- Criar `src/api/main.py` com FastAPI (endpoints `/tarefas/coletar`,
  `/tarefas/treinar`, `/tarefas/recomendar`, `/health`)
- Deploy dos 2 services no Render (API + Dashboard)
- Configurar GitHub Actions com crons diários
- Configurar UptimeRobot para keep-alive

---
### [v2.0] Migração fonte de dados: Investidor10 → Fundamentus + Yahoo + Orquestrador
**Data:** 2026-04-14  
**IA:** Claude Sonnet 4.5 via Claude Code

#### O que foi feito

**Renomeação:**
- `src/data/scraper_indicadores.py` → `src/data/scraper_investidor10.py` (via `git mv`, histórico preservado)

**Novos arquivos em `src/data/`:**
- `scraper_fundamentus.py` — coleta via lib `fundamentus` (raspagem do fundamentus.com.br)
- `scraper_yahoo.py` — coleta via `yfinance .info` (snapshot atual, sem histórico)
- `scraper_orquestrador.py` — coleta com fallback em cascata: Fundamentus → Yahoo → Investidor10

**Atualização de imports:**
- `src/models/recomendador_acoes.py` linha 8: `scraper_indicadores` → `scraper_fundamentus`
- `scripts/executar_tarefas_diarias.py` linha 10: `scraper_indicadores.main` → `scraper_orquestrador.main`

**`requirements.txt`:** adicionado `fundamentus==0.3.2` e `yfinance==1.2.1`

#### Decisões arquiteturais

**Por que 3 scrapers separados?**
Cada fonte cobre lacunas das outras. Os scrapers podem ser executados isoladamente para
diagnóstico de gaps.

**Mapa de cobertura por fonte:**

| Campo | Fundamentus | Yahoo | Investidor10 |
|-------|-------------|-------|--------------|
| payout | ❌ | ✅ (payoutRatio × 100) | ✅ |
| margem_ebitda | ❌ | ✅ (ebitdaMargins × 100) | ✅ |
| p_ebitda | ❌ | ❌ | ✅ |
| ev_ebitda, ev_ebit, p_ebit, p_ativo... | ✅ | parcial | ✅ |
| div_liq_*, patrimonio_ativos... | ✅ calculado | ❌ | ✅ |
| variacao_12m | ✅ via yfinance | ✅ | ✅ |

**Parse do fundamentus (todos strings):**
- `pct`: `"6.6%"` → `float(strip('%'))` = 6.6
- `ratio`: `"574"` → `float(s) / 100` = 5.74
- `fin`: `"1223390000000"` → `float(s)` (valor em R$)
- `direct`: `"49.03"` → `float(s)` (cotação)

**Bancos (ITUB4, BBAS3, etc.):** fundamentus não retorna `Div_Liquida` nem `EBIT_12m`
(estrutura contábil diferente). O scraper detecta isso via `eh_banco` e grava NULL
nesses campos — sem erro, sem quebra. 7 campos ficam NULL para bancos mesmo com fallback
(ev_ebitda, p_ebitda, p_ativo_circ_liq, div_liq_*, div_bruta_patrimonio).

**Orquestrador sequencial (não paralelo):** Cada ticker chama até 3 fontes em série.
Paralelizar introduziria race conditions nos rate limits simultâneos das 3 fontes.

**Resultado do smoke test (PETR4):**
- Fundamentus: 28/31 campos
- Yahoo: +2 (margem_ebitda, payout)
- Investidor10: +1 (p_ebitda)
- **Total: 31/31 campos preenchidos**

#### Diagnóstico de cobertura — 148 tickers testados

**Fundamentus: 142/148 OK (96%)**

8 tickers falham com `No tables found` (HTML divergente no fundamentus.com.br):
`EMBR3, ELET3, ELET6, ARZZ3, TRPL4, RRRP3, MRFG3, GUAR3`

Para esses 8:
- Yahoo também falha (sufixo `.SA` não reconhecido no Yahoo Finance)
- Investidor10 funciona → 29/31 campos (nulos: `margem_ebitda`, `p_ativo_circ_liq`)
- `html5lib==1.1` adicionado ao requirements (dependência do fundamentus para HTML complexo)

**Confirmação do orquestrador:** o `_mesclar()` já operava sobre todos os 31 campos,
portanto qualquer NULL do fundamentus (estrutural ou por falha de ticker) é preenchido
automaticamente pelas fontes de fallback. Nenhuma mudança de lógica foi necessária.

#### Pendências / próximos passos
- Investigar por que os 8 tickers retornam HTML sem tabelas no fundamentus (pode ser
  bloqueio temporário ou estrutura de página diferente para alguns setores)
- Investigar se os 7 campos NULL de bancos impactam o modelo (ML usa fillna(0))
- Avaliar se `beautifulsoup4` pode ser removido quando o Investidor10 não for mais fallback

---
### [v2.6] Normalização de API_URL nos workflows
**Data:** 2026-04-14  
**IA:** Auto via Cursor

#### O que foi feito
- Em `.github/workflows/coletar.yml`, `.github/workflows/treinar.yml` e `.github/workflows/recomendar.yml`: normalização da URL base via:
  - `BASE_URL="${{ secrets.API_URL }}"`
  - `BASE_URL="${BASE_URL%/}"`
- Endpoints `curl` alterados de `"${{ secrets.API_URL }}/tarefas/..."`
  para `"$BASE_URL/tarefas/..."`.

#### Decisões e motivos
- Evitar URLs com `//tarefas/...` quando `API_URL` no secret termina com `/`.
- Tornar workflow robusto sem depender de formato exato do secret.

#### Pendências / próximos passos
- Confirmar novos logs GitHub Actions com `POST /tarefas/...` (sem dupla barra).
- Rodar smoke test de `Treinar` e `Recomendar` no app Railway.

---
### [v1.1] Run pela IDE + mensagem quando falta `.pkl`
**Data:** 2026-04-13  
**IA:** Auto via Cursor

#### O que foi feito
- Em `src/models/classificador.py`, `src/models/regressor_preco.py`, `src/models/recomendador_acoes.py` e `src/data/scraper_indicadores.py`: antes dos `from src....`, inserir na `sys.path` a raiz do repositório (`Path(__file__).resolve().parent...parent`), para o botão **Run** da IDE funcionar sem `PYTHONPATH=.`.
- Em `src/models/recomendador_acoes.py`, função `carregar_artefatos_modelo()`: `FileNotFoundError` com texto orientando treino do classificador (PowerShell e bash) e caminho esperado de `modelo/modelo_classificador_desempenho.pkl`.
- Em `.gitignore`: pós-reorg — `modelo/*.pkl`, `cache_status/`, `cache_results/`, `backups/` (removidos caminhos antigos `insight/app/...`).

#### Decisões e motivos
- Bootstrap local em arquivos “executáveis” evita depender só de configuração da IDE; Docker já usa `PYTHONPATH=/app`, sem conflito.

#### Pendências / próximos passos
- Alinhar `docs/INSTALACAO.md`, `docs/TROUBLESHOOTING.md`, `docs/ARQUITETURA.md` com caminhos `src/` e comandos `docker compose exec ... python src/...` (ainda há referências a `app/` e `classificador.py` na raiz do container antigo).
- Opcional: `.vscode/launch.json` com `cwd` = raiz do repo e `env.PYTHONPATH` = `.` para padronizar equipe.

---
### [v1.0] Reorganização do repositório (layout profissional)
**Data:** 2026-04-13  
**IA:** Auto via Cursor

#### O que foi feito
- Removida pasta wrapper `insight/`; na raiz do repo: `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `.env.example`, pasta `docs/` (mesmos `.md` que estavam em `insight/docs/`).
- Novo layout: `src/core/db_connection.py`, `src/data/scraper_indicadores.py`, `src/models/{classificador,recomendador_acoes,regressor_preco}.py`, `src/dashboard/{app.py,callbacks.py,pages/,assets/}` com `__init__.py` nos pacotes.
- `scripts/backup.py` e `scripts/executar_tarefas_diarias.py`; `BACKUP_DIR` em `backup.py` aponta para `<raiz>/backups/`.
- Pasta `tcc files/` renomeada para `tcc/`.
- Imports internos passaram a `from src....`; `docker-compose`: `dashboard` → `python src/dashboard/app.py`, `scheduler` → `python scripts/executar_tarefas_diarias.py`; volume `backups` → `/app/backups`.
- `Dockerfile`: `COPY src/` e `COPY scripts/`, `ENV PYTHONPATH=/app`, `CMD` padrão apontando para scheduler.
- `src/dashboard/pages/previsoes.py`: diretórios de cache na raiz (`cache_status/`, `cache_results/`), não mais sob `dashboard/`.
- `classificador.py` e `recomendador_acoes.py`: diretório de modelos `<raiz>/modelo/` via `_PROJECT_ROOT` (compatível com volume Docker `modelo:/app/modelo`).
- `README.md`: árvore de pastas e exemplos de execução com `PYTHONPATH=.` e caminhos novos.

#### Decisões e motivos
- `src/` separa biblioteca de aplicação; `scripts/` deixa explícitos entrypoints operacionais (backup, agendador); raiz única simplifica Docker e clone do repo.

#### Pendências / próximos passos
- (Mesmas da v1.1 sobre documentação em `docs/` e launch.json opcional.)

---