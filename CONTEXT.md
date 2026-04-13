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