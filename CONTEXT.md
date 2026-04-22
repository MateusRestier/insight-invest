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
### [v2.21] Atualização de dados em produção sem redeploy
**Data:** 2026-04-22
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**`src/core/db_connection.py`**
- Adicionado `conn.autocommit = True` logo após `psycopg2.connect()`
- Antes: psycopg2 abria uma transação implícita (`BEGIN`) a cada `get_connection()`, e o PostgreSQL servia dados do snapshot do início da transação — ignorando commits feitos pelo scraper depois do deploy
- Com `autocommit=True`: cada query vê o estado mais recente do banco (sem snapshot de transação isolado)

**`src/dashboard/pages/indicadores.py`**
- `dcc.Interval(id='data-load-interval')` ajustado para **1 hora** (`interval=60 * 60 * 1000`)
- Callback `load_comparison_data` reescrito com lógica de horário:
  - **Recarrega** do banco quando o store está vazio (primeira carga da sessão) OU quando `datetime.now().hour == 1` (1h da manhã)
  - **`no_update`** em todos os outros casos (store já populado e não é 1h)
  - `State('comparison-data-store', 'data')` adicionado ao callback para verificar se store já tem dados
- Efeito: banco é consultado uma vez por sessão ao abrir o app, e volta a ser consultado às 1h da manhã de cada dia (janela alinhada com a execução do scraper) — sem consumo desnecessário na Railway

#### Decisões e motivos

- **`autocommit=True` em vez de `COMMIT` explícito**: a causa raiz era o isolamento de transação do PostgreSQL (modo `READ COMMITTED`). Com `autocommit`, não há transação implícita — cada `SELECT` vê o estado atual. Alternativa de fechar/reabrir conexão também funcionaria, mas o `autocommit` é mais simples e sem overhead.
- **Intervalo de 1h com check de horário em vez de 20h fixo**: intervalo de 20h garante no máximo 1 recarga por dia, mas não é determinístico — se o app reinicia às 22h, a próxima atualização seria às 18h do dia seguinte (depois que o scraper já rodou). Com 1h + `hour == 1`, a janela é fixa: sempre às 1h da manhã, 1–2h após a coleta do scraper. Consome apenas 24 "disparos" de interval por dia, cada um apenas verificando a hora (sem I/O se não for 1h).
- **`State` em vez de segundo `Input`**: o store só deve disparar recarga quando o interval dispara, não quando os dados chegam — por isso `State` é correto aqui.

#### Pendências / próximos passos
- Validar no Railway após redeploy que os dados do scraper aparecem no dia seguinte sem redeploy manual.

---
### [v2.20] Conversão para single-page + interatividade do pie chart
**Data:** 2026-04-16
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**Conversão para single-page com scroll anchors (`app.py`, `callbacks.py`, `style.css`)**

- Removido o sistema de roteamento por pathname (`render_page` callback eliminado)
- `app.py` agora importa os 3 layouts diretamente e os renderiza em sequência dentro de `html.Div` com IDs de seção: `section-indicadores`, `section-previsoes`, `section-recomendador`
- NavLinks migrados de `href="/"` para `href="#section-*"` com `external_link=True` e `id` individuais
- `dcc.Location(id="url")` mantido apenas para rastrear o hash da URL (active state)
- `callbacks.py`: adicionado `clientside_callback` que lê `url.hash` e seta `active` nos 3 NavLinks no cliente (zero round-trip ao servidor)
- `style.css`: `html { scroll-behavior: smooth }`, `scroll-margin-top: 70px` nas seções, navbar com `position: sticky; top: 0; z-index: 1000` e `border-bottom: 1px solid #000`
- Espaçamento entre seções: `mb-4` em todos os wrappers de seção
- Recomendador envolvido em `dbc.Container(fluid=True)` para alinhar largura com os demais cards

**Interatividade do gráfico de pizza (`indicadores.py`)**

- Adicionado `dcc.Store(id='pie-click-store')` para guardar a fatia selecionada (toggle)
- Adicionado `dcc.Store(id='comparison-data-store')` + `dcc.Interval(id='data-load-interval', max_intervals=1)` para cache de dados — a query ao banco ocorre **uma única vez** no load; todos os callbacks subsequentes leem do store (zero DB em interações)
- **Callback 1** (`store_pie_click`): `clickData` → store com toggle (clique na mesma fatia desfaz seleção)
- **Callback 2** (`plot_error_distribution`): reconstrói o pie com pull destacado (0.16) na fatia ativa e opacidade 35% nas demais; legenda agora clicável (`itemclick="toggle"`, `itemdoubleclick="toggleothers"`)
- **Callback 3**: `update_table` recebe `pie-click-store` como Input e aplica filtro adicional por categoria de erro
- **Callback 4** (`highlight_pie_from_table`): `active_cell` da tabela → destaca fatia correspondente; usa dados da própria tabela (sem banco)
- `_build_pie_figure()` e `_apply_filters()` extraídas como helpers internos para reutilização entre callbacks
- `_loading_figure(bgcolor)`: figura dark-themed ("Carregando dados...") usada como placeholder inicial dos dois gráficos — elimina o flash branco no carregamento
- `dcc.Loading` com `delay_show=800` — spinner só aparece se o load demorar mais que 800ms
- Cursor `pointer` via CSS + hovertemplate com hint "Clique para filtrar a tabela" (itálico, herda cor do tooltip)
- Legenda do pie agora acima do gráfico (`y=1.02`, `yanchor="bottom"`)

#### Decisões e motivos

- **Single-page + anchors em vez de multi-page**: elimina o reload visual ao trocar de "página"; tudo já está renderizado, navegação é puro scroll
- **`clientside_callback` para active state**: zero latência — roda no browser sem passar pelo servidor Python
- **`external_link=True` nos NavLinks**: hash links (`#section-*`) não recarregam a página mesmo com `external_link=True`; o browser trata `#` como fragment navigation
- **`dcc.Store` como cache de dados**: a causa dos 3–4s de loading em toda interação era `_get_comparison_df()` sendo chamada em cada callback (query ao banco). Com store, a query ocorre uma vez e os callbacks filtram em memória (< 50ms)
- **`highlight_pie_from_table` usa `State('table-previsto-real', 'data')`** diretamente em vez do store: a tabela já tem os dados filtrados, não precisa reprocessar
- **`_loading_figure`** com `paper_bgcolor` igual ao card: transição suave de "carregando" para figura real, sem flash branco
- **`no_update` → `_loading_figure`** no pie: `no_update` mantinha a figura padrão branca do Plotly; retornar a figura dark correta desde o início resolve o flash

#### Pendências / próximos passos
- Validar no Railway após redeploy.
- Se o volume de dados crescer muito, considerar paginação server-side na tabela (atualmente carrega tudo no store).

---
### [v2.19] Remoção de CardHeaders e ajustes visuais
**Data:** 2026-04-16
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**`src/dashboard/pages/indicadores.py`**
- Seção 1 ("Ranking por Métrica"): `dbc.CardHeader` removido; título migrado para `html.H5` dentro do `CardBody` com `fontSize: 2.15rem` e cor `#e8e8ff`; dropdown alinhado à direita via `ms-auto` na mesma row do título
- Seção 2 ("Comparação Preço Previsto × Real"): `dbc.CardHeader` removido; título migrado para `html.H5` com `fontSize: 2.15rem`; subtítulo explicativo virou `html.P` com `className="text-muted mb-3"`
- Gráfico de pizza: legenda movida de abaixo para acima do gráfico — `y=-0.02 / yanchor="top"` → `y=1.02 / yanchor="bottom"`; margens ajustadas de `t=10, b=55` para `t=40, b=10`

**`src/dashboard/pages/previsoes.py`**
- `dbc.CardHeader("🔮 Previsão de Preço — Multi-Dia")` removido; título migrado para `html.H5` com `fontSize: 1.85rem` dentro do `CardBody`

**`src/dashboard/pages/recomendador.py`**
- `dbc.CardHeader("📝 Recomendador de Ações")` removido
- Layout refatorado de dois elementos separados (Card esquerdo + coluna solta direita) para **um único `dbc.Card`** contendo ambas as colunas
- Título "📝 Recomendador de Ações" movido para dentro da coluna esquerda da Row interna
- Título "🪄 Indicadores da Ação Selecionada" na coluna direita, alinhado horizontalmente com o título esquerdo (ambos na mesma Row)
- Separador vertical `borderLeft: 1px solid #2a2a3e` entre as colunas, visível apenas em `md+`

#### Decisões e motivos
- **Remoção dos CardHeaders**: a faixa beige/cinza do Bootstrap (`#2a2a45`) criava uma separação visual que competia com o conteúdo. Títulos dentro do `CardBody` integram melhor com o tema escuro e permitem controle total de tipografia.
- **Um único Card no recomendador**: o layout anterior tinha o painel de indicadores como coluna solta sem card, quebrando a consistência visual. Unificar em um card deixa a página com a mesma linguagem dos outros cards do app.
- **Legenda do pie acima**: com o gráfico já tendo `textinfo="percent"` nas fatias, a legenda abaixo criava espaço morto embaixo e empurrava o gráfico para cima desnecessariamente.

#### Pendências / próximos passos
- Validar no Railway após redeploy.

---
### [v2.18] Otimização de RAM no deploy Railway
**Data:** 2026-04-16
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**`requirements.txt`**
- Removidos 3 pacotes sem uso no serviço web:
  - `matplotlib==3.9.3` — nenhum `import matplotlib` encontrado em nenhum arquivo `.py` do projeto; sobrou da época de gráficos estáticos, antes da migração para Plotly
  - `seaborn==0.13.2` — mesmo caso que matplotlib
  - `schedule==1.2.2` — só é usado em `scripts/executar_tarefas_diarias.py`, que não roda no Railway (é o agendador de execução local)

**`src/dashboard/pages/recomendador.py`**
- Removido import de nível de módulo: `from src.data.scraper_orquestrador import coletar_com_fallback as coletar_indicadores`
- Import movido para **dentro** do callback `update_indicators`, imediatamente antes do primeiro uso
- Efeito: `yfinance`, `fundamentus`, `beautifulsoup4`, `html5lib` e todas as suas dependências transitivas **não são mais carregadas no boot do servidor** — só na primeira vez que o usuário clica em "Recomendar"
- Na segunda chamada em diante, Python reutiliza os módulos já em `sys.modules` sem overhead adicional

#### Decisões e motivos

- **Diagnóstico da cadeia de imports**: `main.py` importa `app.py` no nível do módulo (linha 309) → `app.py` importa `callbacks.py` → `callbacks.py` importa todos os três módulos de página imediatamente → `recomendador.py` importava `scraper_orquestrador` no topo → `scraper_orquestrador` importa `scraper_fundamentus` e `scraper_yahoo` no topo → ambos importam `yfinance` e `fundamentus`. Resultado: ~100–150 MB de libs de scraping carregadas no boot, mesmo sem nenhum request ao Recomendador.
- **Lazy import em vez de refatorar callbacks**: a solução mais cirúrgica — uma linha de mudança, sem alterar contratos, sem risco de regressão. Python cacheia módulos em `sys.modules`, então o custo de execução do `import` só ocorre uma vez por processo.
- **Remoção de dependências vs. manter por segurança**: matplotlib/seaborn confirmados ausentes via `grep` em todo o repositório (zero matches). Remover dependências não utilizadas é sempre preferível — reduz tempo de build, tamanho da imagem e superfície de ataque.

#### Economia estimada
- `matplotlib` + `seaborn`: ~100 MB (instalação + carregamento)
- `yfinance` + `fundamentus` + `bs4` + `html5lib` (lazy): ~100–150 MB fora do baseline do processo
- **Total esperado: ~200–250 MB de redução no uso de RAM em idle**

#### Pendências / próximos passos
- Acompanhar gráfico de RAM no Railway após redeploy para confirmar a redução.
- Se RAM ainda estiver alta após o deploy, investigar se `scikit-learn`/`joblib` estão sendo importados em algum ponto do boot (via `recomendador_acoes.py`).

---
### [v2.17] Reformulação do gráfico de pizza (indicadores)
**Data:** 2026-04-15
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**`src/dashboard/pages/indicadores.py`**

- Adicionado `import plotly.graph_objects as go` no topo do arquivo.
- Gráfico de distribuição de erros (`pie-error-dist`) completamente refeito:
  - Migrado de `px.pie` para `go.Pie` para controle total sobre o layout
  - Pizza sólida (`hole=0`) com `pull=[0.06, 0.06, 0.06]` em todas as fatias — efeito "explodido" que remete ao 3D minimalista
  - `textinfo="percent"` com `textposition="inside"` e `textfont` branco — porcentagens dentro de cada fatia, limpas e legíveis
  - Sem texto externo nem título no gráfico — toda informação complementar via hover e legenda
  - Hover customizado: `"<b>%{label}</b><br>%{value} previsões — %{percent}"`
  - Legenda horizontal abaixo (`orientation="h"`, `y=-0.02`, `x=0.5`)
  - `itemclick=False, itemdoubleclick=False` — legenda decorativa, não interativa
  - Labels renomeados de "Igual a 0"/"Maior que 0"/"Menor que 0" para "Preciso"/"Errou pra mais"/"Errou pra menos" — consistência com a legenda da tabela
  - Cores idênticas à legenda da tabela: `#00cc96`, `#60a5fa`, `#a78bfa`
  - `plot_bgcolor="rgba(0,0,0,0)"` e `paper_bgcolor="#2c2c3e"`
  - Margens compactas: `l=10, r=10, t=10, b=55`

#### Decisões e motivos

- **Pizza sólida + pull** em vez de donut: o furo central exigia annotations de texto para ter utilidade; sem texto no centro, o donut vira "espaço vazio desnecessário". A pizza sólida com separação entre fatias tem mais massa visual e o `pull` cria profundidade sem precisar de 3D real.
- **Sem título no gráfico**: o contexto já é dado pelo `CardHeader` da seção. Título dentro do Plotly ocupava espaço sem agregar.
- **Legenda não-interativa**: com apenas 3 categorias fixas, clicar para esconder uma fatia não tem utilidade prática e poderia confundir o usuário.
- **Porcentagens dentro das fatias** (`textposition="inside"`): mais limpo que fora — não cria linhas de conexão e não sai do gráfico.

#### Pendências / próximos passos

- Validar no Railway se fatias muito pequenas (< ~5%) ficam legíveis com texto dentro; se não, considerar `textposition="auto"`.

---
### [v2.16] Reformulação da página Recomendações
**Data:** 2026-04-15
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**`src/dashboard/pages/recomendador.py`**

**Gráfico gauge:**
- Cores das zonas (steps) clareadas para contraste visível contra o fundo `#1e1e2f`:
  - Zona 0–50: `#2e1a1a` → `#3d2020` (vermelho-escuro saturado)
  - Zona 50–100: `#1a2e1a` → `#1a3d2c` (verde-escuro saturado)
- `bgcolor` do gauge: `#1e1e2f` → `#252535` (leve elevação para criar profundidade)
- Linha do threshold: `#e0e0e0` → `#9b9bb5` (branco puro chamava atenção demais)

**Blocos de resultado (indicadores-chave, pontos positivos/atenção):**
- Removidos `positivos_block`, `negativos_block` e `accordion_items` — eram código morto (criados mas nunca usados no `return`; o accordion duplicava o conteúdo)
- `indicadores_block`: substituído de `dbc.Table` genérico por linhas flexbox com:
  - Nome à esquerda em `#9b9bb5`, valor à direita em monospace
  - Cor semântica nos valores percentuais: verde `#00cc96` se positivo, vermelho `#ff6b6b` se negativo
  - Fundo `#2c2c3e` com `border-radius: 6px`
- Pontos Positivos: card com fundo `#162820` + `borderLeft: 3px solid #00cc96`
- Pontos de Atenção: card com fundo `#231c0e` + `borderLeft: 3px solid #f59e0b`
  - Cor alterada de `#ffcc00` (amarelo gritante) para `#f59e0b` (âmbar quente, coerente com a paleta)
- Accordion (`dbc.Accordion`) removido — substituído por blocos sempre visíveis com design totalmente controlado via inline styles

**Correção de bugs nos grupos de indicadores:**
- Bug: `_INDICATOR_GROUPS` usava `dy`, `valor_firma_ebit`, `valor_firma_ebitda`, mas o scraper retorna `dividend_yield`, `ev_ebit`, `ev_ebitda`, `p_ebitda`, `p_ebit`, `p_ativo`, `p_cap_giro`, `p_ativo_circ_liq`. Nenhum era reconhecido pelos grupos, todos caíam no fallback → gerava duas seções "Outros"
- Fix: grupos expandidos com ambos os nomes possíveis para cada campo (ex: `"ev_ebitda", "valor_firma_ebitda"`)
- `_DISPLAY_NAMES` expandido com todos os nomes corretos: "EV/EBITDA", "EV/EBIT", "P/EBITDA", "P/EBIT", "P/Ativo", "P/Cap. Giro", "P/Ativo Circ. Líq."
- `_PERCENT_KEYS` expandido com `dividend_yield` (estava apenas `dy`)
- Grupo "Outros" renomeado para "Liquidez & Crescimento"
- DY agora aparece em "Dividendos" com `%` corretamente

**Cor semântica nos cards de indicadores:**
- Adicionado `_SIGNED_KEYS`: conjunto de campos onde positivo = bom (margens, ROE, ROIC, ROA, DY, Variação 12M)
- `_make_card` atualizado com `_valor_color()`: valor verde se positivo, vermelho se negativo, neutro para ratios
- Label em `#9b9bb5` (tom secundário), valor em monospace `1rem`

**Seção "Destaques" no topo dos indicadores:**
- Adicionada `_HIGHLIGHT_KEYS` com os 6 indicadores que os investidores olham primeiro: Cotação, P/L, P/VP, Dividend Yield, ROE, Variação 12M
- `_make_highlight_card()`: card maior (`1.3rem`, padding `14px`), fundo `#2c2c3e`, borda `rgba(85,97,255,0.3)`
- Seção "DESTAQUES" com header em `#b0b8ff` + `borderBottom: 1px solid #5561ff` — visualmente mais proeminente que os grupos normais
- Deduplicação de `dy`/`dividend_yield` — só aparece uma vez no destaque
- Os mesmos campos aparecem também nos grupos detalhados abaixo (destaque = resumo rápido, grupos = contexto completo)

#### Decisões e motivos

- **Accordion removido**: componente Bootstrap com estilo divergente do tema escuro personalizado. Blocos custom com inline styles dão controle total sem dependência de CSS de terceiro.
- **Fundo tintado nos pontos**: `#162820` (verde muito escuro) e `#231c0e` (âmbar muito escuro) criam identidade visual clara para cada seção sem brigar com o tema geral.
- **Dois nomes por campo no grupo**: melhor que renomear campos no scraper (breaking change no banco) ou fazer mapeamento reverso. Incluir ambos os nomes no grupo garante compatibilidade com qualquer versão do scraper.
- **Destaques repetem nos grupos**: padrão "KPI cards no topo + tabela completa abaixo" — o usuário tem visão rápida e contexto completo sem precisar rolar.

#### Pendências / próximos passos

- Validar deploy Railway.
- Se o scraper vier a ser normalizado para nomes únicos por campo, limpar os aliases duplicados nos grupos.

---
### [v2.15] Reformulação visual das tabelas DataTable
**Data:** 2026-04-15
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**`src/dashboard/pages/indicadores.py`**

- Importado `Format, Scheme, Sign` de `dash.dash_table.Format` para formatação numérica tipada.
- Tabela `table-previsto-real` completamente reestilizada:
  - `style_table`: `borderRadius: 8px`, `border: 1px solid #2a2a3e`
  - `style_header`: fundo `#2a2a45`, texto `#e8e8ff` (quase branco), uppercase, `fontSize: 0.7rem`, `letterSpacing: 0.08em`, `borderBottom: 1px solid #5561ff` apenas
  - `style_cell`: fundo `#1e1e2f`, apenas `borderBottom: 1px solid #2a2a3e` (sem grade tipo Excel)
  - `style_cell_conditional`: coluna Ação à esquerda + `#b0b8ff`; colunas numéricas à direita + monospace; datas em `#7a7a9a`
  - `style_data_conditional`: linhas zebradas `#232336`, seleção roxa, e cores da coluna Erro %
  - `style_header_conditional`: oculta coluna auxiliar `_cor_erro`
- Nomes das colunas revisados: `data_calculo` → "Gerada em", `data_previsao` → "Data Alvo", `preco_previsto` → "Previsto (R$)", `preco_real` → "Real (R$)"
- Subtítulo explicativo adicionado no `CardHeader` da seção
- Legenda de cores adicionada acima da tabela
- Filtros renomeados para "Data Alvo" e "Gerada em" (consistência com colunas)
- `tooltip_header` com descrição de cada coluna (aparece ao hover no header)

**Correção de bug — cores da coluna Erro % não apareciam:**
- Causa 1: `filter_query` com `&&` (ex: `{erro_pct} > 0 && {erro_pct} <= 5`) não faz match confiável no `style_data_conditional` — depende da versão do Dash.
- Causa 2: `Format(sign=Sign.positive)` converte o valor numérico para string `"+0.14"` antes do `filter_query` avaliar — comparação numérica falha silenciosamente.
- Causa 3 (CSS): `.dash-cell { color: #e0e0e0 !important }` no `style.css` bloqueava qualquer inline style injetado pelo Dash via `style_data_conditional`.
- **Fix definitivo**: coluna auxiliar `_cor_erro` com categorias string (`"zero"`, `"pos"`, `"neg"`) computadas em Python antes de `to_dict('records')`. O `filter_query` usa comparação de string (`{_cor_erro} = "pos"`), que é infalível. A coluna fica oculta via `display: none` em `style_cell_conditional` e `style_header_conditional`.
- Simplificado de 5 faixas (vermelho/laranja/azul/roxo) para **3 categorias de igual peso visual**:
  - `#00cc96` verde → acerto preciso (= 0)
  - `#60a5fa` azul céu → errou pra mais (> 0)
  - `#a78bfa` violeta suave → errou pra menos (< 0)
  - Azul e violeta têm luminosidade equivalente — nenhum parece "pior" que o outro

**`src/dashboard/pages/previsoes.py`**

- Importado `Format, Scheme` de `dash.dash_table.Format`.
- Tabela `table-previsao` reestilizada com o mesmo visual da tabela de indicadores:
  - Mesmos `style_table`, `style_header`, `style_cell` (sem grade, zebra, borderBottom apenas)
  - `style_cell_conditional`: Ação à esquerda `#b0b8ff`, Previsto e Dias à Frente à direita monospace, Data Alvo em `#7a7a9a`
- Colunas do callback `update_progress` atualizadas: `_col_map` com nomes amigáveis + `Format(precision=2)` no `preco_previsto`; nome `data_previsao` → "Data Alvo"

**`src/dashboard/assets/style.css`**

- Removido `color: #e0e0e0 !important` do seletor `.dash-cell` — esse `!important` era a causa raiz do bloqueio das cores condicionais. Mantido apenas `background-color: #2c2c3e !important` (necessário para sobrescrever o fundo branco padrão do Dash).
- Adicionado hover de linha inteira: `.dash-spreadsheet-inner tr:hover td.dash-td-cell { background-color: rgba(85,97,255,0.09) !important }`
- Estilizada a paginação da DataTable: botões com tema escuro (`#2c2c3e`), hover roxo (`#5561ff`), disabled com `opacity: 0.35`
- Fix do input de número de página (texto preto no browser): adicionado `-webkit-text-fill-color: #e0e0e0 !important` — o `color` é ignorado pelo Chrome/Safari para inputs de formulário; o `-webkit-text-fill-color` sobrescreve o estilo nativo do browser
- Adicionado estilo de tooltip da DataTable: `#1e1e2f`, borda `#444`, `border-radius: 4px`

#### Decisões e motivos

- **Coluna auxiliar oculta** em vez de `filter_query` numérico: Dash DataTable `filter_query` opera em valores *formatados* quando `Format` é aplicado, não nos valores brutos. Usar uma categoria string pré-computada em Python é a única abordagem 100% confiável para coloração condicional.
- **3 cores de igual luminosidade** para Erro %: evita hierarquia de gravidade implícita. Vermelho/laranja vs. azul sugere que errar pra mais é pior que errar pra menos — o que não é verdade neste contexto.
- **`borderBottom` apenas**: tabelas financeiras modernas (Bloomberg, XP, etc.) usam apenas separadores horizontais. Grade completa remete ao Excel e envelhece o visual.
- **`-webkit-text-fill-color`**: propriedade CSS específica para WebKit que tem precedência sobre o estilo nativo de formulários. Necessária quando `color !important` não é suficiente para campos `<input>` no Chrome/Safari.

#### Pendências / próximos passos

- Validar deploy Railway com as 3 alterações.
- Verificar se o hover de linha funciona corretamente no Safari (WebKit pode renderizar `.dash-td-cell` diferente).

---
### [v2.14] Redesign completo de UX/UI do frontend (Dash + Bootstrap)
**Data:** 2026-04-14  
**IA:** Claude Sonnet 4.6 via Claude Code

#### O que foi feito

**Migração de tema e roteamento (`app.py`, `callbacks.py`)**

- Tema migrado de `dbc.themes.LITERA` (claro) para `dbc.themes.DARKLY` (escuro nativo). Antes, todo o dark mode era forçado via `!important`, conflitando com o tema claro; o DARKLY elimina a maioria desses conflitos e provê alertas, badges, tabelas e acordeão no tema certo por padrão.
- Roteamento substituído: o sistema anterior usava `n_clicks` de botões e `dcc.Tabs` para trocar de página, perdendo a URL ao navegar (F5 resetava para a home). Substituído por `dcc.Location(id="url") + dbc.NavLink(active="exact")`: cada página agora tem URL própria (`/`, `/previsoes`, `/recomendador`), bookmarkável e resistente a F5.
- `callbacks.py` enxugado de ~70 linhas de lógica `ctx.triggered` / `no_update` para um callback de 4 linhas (`render_page` por `pathname`). Os callbacks de active-state dos NavLinks foram eliminados (gerenciados automaticamente pelo DBC com `active="exact"`).
- Título do app definido: `title="Insight Invest"`.
- Navbar com `style={"padding": "0.5rem 1rem"}` para respiração vertical mínima; brand com `font-weight: 600; letter-spacing: 0.02em`.

**Sistema de cores (`style.css`)**

Hierarquia de três camadas definida definitivamente:
- `#13131f` — fundo geral da página (`body`)
- `#1e1e2f` — cards de seção (os dois grandes blocos do indicadores, cards gerais)
- `#2c2c3e` — navbar, inputs, cards internos (performance, recomendação top-10), fundo de tabela, fundo do gráfico de pizza

Outros ajustes de cor:
- `.recomendacao-positiva`: `green` → `#00cc96 !important`
- `.recomendacao-negativa`: `red` → `#ff6b6b !important`
- `.card-header.text-center` (seletor anterior: `.card .text-center`) — corrige contaminação indesejada de outros elementos com classe `text-center`
- Hover no Dash DataTable: fundo `rgba(126,135,255,0.04)` + número `#b0b8ff` (antes ficava branco, ilegível)
- Gauge do recomendador: `paper_bgcolor="rgba(0,0,0,0)"` — Plotly não aceita `"transparent"` (CSS keyword), apenas formatos de cor explícitos. Bug seria `ValueError: Invalid value`.

**Filtros na página Indicadores (`indicadores.py`)**

- Filtros de data migrados de `dcc.Dropdown` (lista de strings) para `dbc.Input(type="date", className="input-dark")` com `color-scheme: dark` no CSS para o seletor nativo do browser respeitar o tema escuro.
- Layout dos 4 filtros reestruturado de `dbc.Row`/`dbc.Col` (Bootstrap grid) para `html.Div(className="filtros-indicadores")` + `html.Div(className="filter-col")`. Motivo: `dbc.Col` + react-select têm width intrínseca mínima que excedia o espaço disponível, forçando quebra de linha. O padrão CSS `flex: 1 1 0; min-width: 0` garante divisão igual independente do conteúdo.
- `dbc.Label` adicionado a todos os 4 filtros para alinhamento vertical uniforme (dropdowns antes não tinham label e ficavam mais baixos).
- `overflow: hidden` **não** foi adicionado ao `.filter-col` — isso teria clipado o menu suspenso do react-select, que é `position: absolute`. O `min-width: 0` é suficiente para evitar expansão da coluna.
- Callbacks `populate_previsao_options` e `populate_calculo_options` eliminados. As datas agora vêm diretamente do input.
- `_get_comparison_df()` passou a converter datas para string antes de retornar, corrigindo bug silencioso nos filtros de data.

**Layout da página Indicadores (`indicadores.py`)**

- Página dividida em dois `dbc.Card` com `dbc.CardHeader` distintos: "Ranking por Métrica" e "Comparação Preço Previsto × Real". Antes era tudo em um bloco sem hierarquia visual clara.
- `dcc.Loading(type="dot", color="#5561ff")` envolvendo tabela + gráfico de pizza — feedback visual de carregamento sem spinner de tela cheia.
- Cards de performance do modelo: layout vertical com `html.P` (label) + `html.H4` (valor), usando classes `.performance-card`, `.metric-label`, `.metric-value`. Antes eram genéricos e sem distinção visual.
  - Métricas: MAE/MSE/RMSE formatados com 4 casas decimais; R² em %, MAPE em %.
- Sidebar de recomendação renomeada: "Classificação das Ações à Esquerda" → "Recomendação do Modelo".
- `hoverData` **removido** do callback `plot_error_distribution`. O input `Input('pie-error-dist', 'hoverData')` causava um round-trip completo ao banco a cada movimento de mouse no gráfico. O hover nativo do Plotly trata a interação no frontend sem callback.
- `plot_bgcolor`/`paper_bgcolor` do gráfico de pizza: `#2c2c3e` (via parâmetro Python, não CSS).

**Recomendador (`recomendador.py`)**

- Output do recomendador migrado de `html.Pre` (bloco de texto terminal) para layout estruturado com componentes Bootstrap:
  - `dbc.Alert` (verde/vermelho) para veredicto — ticker + resultado
  - `go.Indicator` gauge (modo `gauge+number`) para probabilidade "Recomendada" — barra verde (#00cc96) ou vermelha (#ff6b6b), fundo `paper_bgcolor="rgba(0,0,0,0)"`, `height=190`
  - `dbc.Table` para indicadores-chave (tabela compacta borderless com fundo transparente)
  - `dbc.Accordion(always_open=True, flush=True)` para Pontos Positivos e Pontos de Atenção — sem callbacks, expansão gerenciada pelo componente DBC
- `dbc.Input(className="input-dark")` substituindo `dcc.Input` (consistência visual com os demais inputs do app)
- Indicadores da ação organizados em 5 grupos semânticos: Valuation, Rentabilidade, Dividendos, Endividamento, Outros. Cada grupo tem caption com `textTransform: uppercase; fontSize: 0.7rem; color: #9b9bb5`.
- Erros retornam `dbc.Alert(color="danger"/"warning")` em vez de texto puro.

**Previsões (`previsoes.py`)**

- DataTable com `style_header={"backgroundColor":"#5561ff","color":"#ffffff","fontWeight":"bold"}` e `style_cell={"backgroundColor":"#1e1e2f"}` para consistência de tema.
- Botão "Carregar" → "Gerar Previsão".
- Inputs organizados em colunas separadas com `dbc.Label` ("Ticker" / "Dias à frente").

**CSS responsivo (`style.css`)**

- `.filtros-indicadores`: quebra para 2 por linha em ≤768px; 1 por linha em ≤480px
- `.performance-cards-row`: quebra para 2 por linha em ≤900px; coluna única em ≤600px
- Navbar brand: fonte menor em ≤576px; nav-items empilhados

#### Decisões e motivos

- **DARKLY em vez de continuar forçando dark mode no LITERA**: o custo de manutenção dos `!important`s crescia a cada componente novo (acordeão, badges, alertas). O DARKLY fornece base correta; nossos `!important`s restantes só cobrem o tom roxo-escuro do palette, não o combate ao tema claro.
- **CSS flexbox puro nos filtros** (em vez de dbc.Col): react-select tem um minimum intrinsic width que o Bootstrap grid não consegue forçar para zero. `flex: 1 1 0; min-width: 0` é a forma correta de dividir espaço igualmente sem depender do conteúdo.
- **Não usar `overflow: hidden` em `.filter-col`**: menus de `position: absolute` escapam do fluxo normal e não causam overflow; adicionar `hidden` os clipa sem necessidade.
- **Remover hoverData do pie**: o padrão de "callback para realçar fatia no hover" é um antipadrão no Dash — força round-trip ao servidor a cada frame de mouse. Plotly faz highlight de hover nativamente no cliente.
- **`rgba(0,0,0,0)` em vez de `"transparent"`**: Plotly usa seu próprio validador de cores, não o CSS. Strings sem prefixo `rgba/rgb/hex` são rejeitadas com `ValueError`.

#### Pendências / próximos passos

- Validar deploy no Railway após push (6 arquivos modificados).
- Testar em mobile (320px) o layout dos filtros em 1 coluna e os cards de performance empilhados.
- Avaliar se o gráfico de pizza precisa de altura mínima maior em telas muito pequenas (hoje `min-height: 300px`).

---
### [v2.13] Cron mensal para treino no GitHub Actions
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`.github/workflows/treinar.yml`**:
  - cron alterado de diário para mensal.
  - novo agendamento:
    - `0 4 1 * *` (04:00 UTC = 01:00 BRT, no dia 1 de cada mês).
  - `workflow_dispatch` mantido para execução manual quando necessário.

#### Decisões e motivos

- Solicitação do usuário para reduzir frequência de treino automático e concentrar rotina mensal.

#### Pendências / próximos passos

- Validar na aba Actions se próximo agendamento automático está correto.
- Manter execução manual disponível para re-treinos emergenciais.

---
### [v2.12] Relatório detalhado no recomendador via API
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`src/api/main.py`**:
  - endpoint `POST /recomendacao/{ticker}` ampliado para retornar:
    - `indicadores_chave`
    - `justificativas_positivas`
    - `justificativas_negativas`
  - adicionada lógica heurística no endpoint para compor justificativas em formato estruturado.
- **`src/dashboard/pages/recomendador.py`**:
  - `update_recommend` passou a renderizar relatório completo:
    - resultado + probabilidades;
    - bloco de indicadores-chave;
    - bloco de pontos positivos;
    - bloco de pontos de atenção.
- **`scripts/treinar_local_e_salvar.py`**:
  - adicionada docstring de uso no topo com comandos de execução e pré-requisitos.

#### Decisões e motivos

- Após migração para recomendação via API, saída no dashboard ficou resumida.
- Usuário solicitou retorno mais rico, como versão anterior.
- Solução escolhida: enriquecer payload da API e manter dashboard apenas como camada de apresentação.

#### Pendências / próximos passos

- Deploy no Railway.
- Validar no app produção com ticker real (ex: `BBAS3`, `PETR4`) se relatório completo aparece.
- Opcional futuro: mover heurísticas para função compartilhada única (evitar duplicação entre API e módulo de recomendação).

---
### [v2.11] Ajuste script local + fix deploy multipart
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`scripts/treinar_local_e_salvar.py`**:
  - novo seletor `--job` com opções `todos`, `classificador`, `regressor`, `recomendacoes`;
  - classificador agora tenta upload automático do `.pkl` para Railway via `POST /modelo/upload`;
  - usa `API_URL` e `API_KEY` do `.env`;
  - adicionada flag `--nao-enviar-modelo`.
- **`requirements.txt`**:
  - adicionado `python-multipart>=0.0.20`.

#### Decisões e motivos

- Deploy falhou após criação de `UploadFile` endpoint com erro:
  - `Form data requires "python-multipart" to be installed.`
- FastAPI exige `python-multipart` para multipart/form-data.
- Usuário pediu execução de jobs locais isolados apontando para persistência no Railway.

#### Pendências / próximos passos

- Fazer redeploy no Railway com dependência nova.
- Testar upload do modelo via endpoint.
- Confirmar recomendador em produção sem erro de modelo ausente.

---
### [v2.10] Upload de modelo + robustez no recomendador
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`scripts/treinar_local_e_salvar.py`** criado:
  - pipeline local único para classificador + regressor + recomendações;
  - flags `--sem-classificador`, `--sem-regressor`, `--sem-recomendacoes`, `--n-dias`, `--data-calculo`.
- **`src/api/main.py`**:
  - novo endpoint `POST /modelo/upload` (multipart) protegido por `X-API-Key`;
  - valida nome `modelo_classificador_desempenho.pkl` e extensão `.pkl`;
  - salva em `/_PROJECT_ROOT/modelo` (no Railway: `/app/modelo` com volume).
- **`src/dashboard/pages/recomendador.py`**:
  - fix para `update_indicators` aceitar retorno de `coletar_indicadores` como `tuple` ou `dict`;
  - elimina erro `ValueError: too many values to unpack (expected 2)` observado em produção.

#### Decisões e motivos

- Treino local não copia automaticamente `.pkl` para Railway; foi necessário criar upload explícito do artefato.
- Logs mostraram que coletor estava OK (`POST /tarefas/coletar 202`), mas o dashboard quebrava em callback do recomendador durante coleta concorrente.
- Também confirmado em log que treino rodou por chamada separada (`POST /tarefas/treinar 202`), não por encadeamento interno do coletor.

#### Pendências / próximos passos

- Deploy das mudanças para liberar `POST /modelo/upload`.
- Enviar `.pkl` local para produção via endpoint novo.
- Validar em produção:
  - `POST /modelo/upload` retorna `ok: true`;
  - recomendador deixa de retornar erro 409 de modelo ausente;
  - callback de indicadores sem erro 500.

---
### [v2.9] Hardening extra coluna `acao` no regressor
**Data:** 2026-04-14
**IA:** Codex 5.3 via Cursor

#### O que foi feito

- **`src/models/regressor_preco.py`**:
  - em `adicionar_preco_futuro()`, `groupby/apply` agora injeta `acao` explicitamente por grupo (`grp.name`) e usa `dropna=False`.
  - em `preparar_dados_regressao()`, adicionado `acao_fallback` antes transformações e restauração por `reindex` caso `acao` suma das colunas.

#### Decisões e motivos

- Logs Railway ainda mostravam `KeyError: "Coluna 'acao' ausente após preparação dos dados de regressão."`.
- Variações de estrutura após `groupby/apply` em pandas podem remover/realocar `acao`.
- Preservar `acao` na origem + fallback defensivo reduz risco entre versões/ambientes.

#### Pendências / próximos passos

- Rodar Action `Treinar Modelos` novamente.
- Confirmar logs sem `KeyError: 'acao'` e sem exceção ASGI.
- Validar fluxo completo: treino, recomendação, aba **Prever preço**.

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