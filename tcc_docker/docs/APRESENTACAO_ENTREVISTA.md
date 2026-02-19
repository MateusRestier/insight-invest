# 🎯 Guia de Apresentação para Entrevista

## Elevator Pitch (30 segundos)

> "Desenvolvi um sistema completo de análise e recomendação de ações da B3 usando Machine Learning. O projeto coleta automaticamente 31 indicadores fundamentalistas de 149 ações, treina dois modelos de Random Forest com validação temporal rigorosa para evitar data leakage, gera recomendações automatizadas e apresenta tudo em um dashboard interativo. O sistema roda diariamente de forma autônoma, fazendo scraping, treinamento, previsões e backup do banco PostgreSQL."

---

## Estrutura de Apresentação (10-15 minutos)

### 1️⃣ INTRODUÇÃO (2 min)

**Contexto:**
- TCC de Ciência da Computação
- Problema: Investidores individuais têm dificuldade em analisar indicadores fundamentalistas
- Solução: Sistema automatizado que usa ML para recomendar ações

**Principais Números:**
- 149 tickers da B3
- 31 indicadores fundamentalistas
- ~134k registros históricos
- Execução diária automática (~10 minutos)

---

### 2️⃣ ARQUITETURA DO SISTEMA (3 min)

**Componentes Principais:**

```
1. COLETA (Scraper)
   → Web scraping paralelo (BeautifulSoup)
   → 149 ações em ~1-2 minutos

2. ARMAZENAMENTO (PostgreSQL)
   → 3 tabelas relacionadas
   → UPSERT idempotente

3. MACHINE LEARNING
   → Classificador (RandomForest): Bom desempenho futuro?
   → Regressor (RandomForest): Qual será o preço em N dias?

4. DASHBOARD (Dash/Plotly)
   → Top-10 ações por métrica
   → Previsões multi-dia sob demanda
   → Recomendações com justificativas

5. ORQUESTRAÇÃO
   → Tarefas diárias às 01:00
   → Backup automático
```

**Stack Tecnológico:**
- Python 3.12, scikit-learn, PostgreSQL, Docker
- Dash/Plotly, BeautifulSoup, ThreadPoolExecutor

---

### 3️⃣ DESAFIOS TÉCNICOS RESOLVIDOS (5 min)

#### ⚡ Desafio 1: Data Leakage Temporal

**Problema:**
> "Modelos financeiros tradicionais frequentemente 'espionam o futuro' durante o treino, inflacionando métricas artificialmente."

**Solução Implementada:**
- ✅ **TimeSeriesSplit:** Validação cruzada que sempre treina com passado e valida com futuro
- ✅ **Hold-out temporal:** 80% histórico para treino, 20% mais recente para avaliação final
- ✅ **merge_asof com direction='forward':** Busca cotação futura real sem vazar informação

**Código-chave:**
```python
# Busca o próximo valor disponível no futuro
df_futuro = pd.merge_asof(
    left=df[['acao', 'data_futura_alvo']],
    right=df[['acao', 'data_coleta', 'cotacao']],
    by='acao',
    direction='forward'  # crucial!
)
```

#### ⚡ Desafio 2: Rotulagem Inteligente

**Problema:**
> "Usar filtros fixos (ex: P/L < 10) é redundante - o modelo só aprende a regra que já criamos."

**Solução:**
- ✅ **Rotulagem por desempenho futuro relativo**
- ✅ **Top 25%** de retorno em 10 dias → Compra
- ✅ **Bottom 25%** → Não compra
- ✅ **Quantis por data** (adapta-se à volatilidade)
- ✅ **Critério duplo:** Top 25% **E** empresa saudável (P/L > 0, ROE > 0)

**Resultado:** Modelo aprende padrões preditivos reais, não regras fixas.

#### ⚡ Desafio 3: Evitar "Comprar no Topo"

**Problema:**
> "Modelo focava em `variacao_12m` (momentum) e recomendava ações já muito valorizadas."

**Solução:**
1. Ajuste `max_features=0.5` → força diversificação de features
2. Critério de qualidade fundamentalista no rótulo
3. Feature `fund_bad` penaliza empresas com prejuízo

#### ⚡ Desafio 4: Justificativas Enganosas

**Problema:**
> "AMER3 tinha P/L=0.5 e ROE=80% (distorções contábeis), mas eram classificados como 'positivos'."

**Solução: Filtros de Sanidade baseados em Value Investing**
```python
if 0 < PL < 2:  # Excessivamente baixo
    return "NEGATIVO - alto risco"

if ROE > 50%:   # Extremamente alto
    return "NEGATIVO - suspeito de distorção contábil"
```

#### ⚡ Desafio 5: Performance Multi-Dia

**Problema:**
> "Prever 10 dias executava pipeline 10 vezes (10 carregamentos de BD!) ~30 minutos."

**Solução: Refatoração**
- Carrega dados **uma única vez**
- Loop leve com modelos especializados por horizonte
- **Resultado:** 10x mais rápido (~3-5 minutos)

---

### 4️⃣ DEMONSTRAÇÃO PRÁTICA (3 min)

**Mostrar Dashboard:**

1. **Aba Indicadores:**
   - Top-10 ações por "Desconto vs Graham"
   - KPIs do modelo (MAE, RMSE, R²)
   - Tabela Previsto × Real

2. **Aba Previsões:**
   - Input: "PETR4" + "10 dias"
   - Barra de progresso em tempo real
   - Tabela com previsões de D+1 até D+10

3. **Aba Recomendador:**
   - Input: "VALE3"
   - Parecer formatado com emojis
   - Análise: Pontos positivos/negativos

**Conectar no DBeaver:**
- Mostrar tabelas populadas
- Query exemplo: Top recomendações

---

### 5️⃣ RESULTADOS E MÉTRICAS (2 min)

**Classificador:**
- Acurácia: 65-75%
- ROC-AUC: 0.70-0.80
- Precision: 70-80%

**Regressor:**
- MAE: R$ 0.50 - 2.00
- R²: 0.85 - 0.95
- MAPE: 5-15%

**Performance Operacional:**
- Scraping: ~1-2 min (149 ações)
- Regressão Multi-Dia: ~3-5 min
- Total Diário: ~7-12 min

---

## Perguntas Frequentes e Respostas

### "Por que Random Forest e não Deep Learning?"

> "Optei por Random Forest porque os dados são **tabulares** (indicadores fundamentalistas pontuais), não sequenciais. Random Forest oferece melhor **interpretabilidade** via feature_importances, é mais **robusto a outliers**, não requer normalização e funciona muito bem em datasets moderados (~134k registros). Deep Learning seria overkill e menos interpretável para este problema."

### "Como você garante que não há data leakage?"

> "Implementei três camadas de proteção: primeiro, uso **TimeSeriesSplit** que nunca treina com dados futuros; segundo, mantenho um **hold-out temporal** separando 20% mais recentes que nunca é visto durante tuning; terceiro, uso **merge_asof com direction='forward'** que busca cotações futuras reais sem vazar informação do passado."

### "O modelo é retreinado automaticamente?"

> "Atualmente não - é treinado uma vez e usado para predições. Uma melhoria futura seria implementar **retreinamento semanal/mensal** com dados novos, usando rolling window para manter o modelo atualizado com padrões de mercado recentes."

### "Como você lida com empresas em crise?"

> "Implementei um **filtro de qualidade fundamentalista**: empresas com P/L ≤ 0 ou ROE ≤ 0 recebem automaticamente rótulo 0 (não compra) e flag 'fund_bad'. Além disso, as **justificativas heurísticas** identificam valores extremos (ex: ROE > 50%) como sinais de alerta de possível distorção contábil."

### "Qual a feature mais importante do modelo?"

> "Através de `feature_importances_`, identifiquei que **preco_sobre_graham** (baseado na fórmula de Benjamin Graham de Value Investing) é consistentemente a feature mais importante (~15%), seguida por P/L (~12%) e ROE (~10%). Isso valida que o modelo aprendeu padrões alinhados com princípios de investimento em valor."

### "Como você mede a acurácia do regressor de preços?"

> "Uso **5 métricas complementares**: MAE (erro absoluto médio em R$), MSE/RMSE (penaliza erros grandes), R² (% da variância explicada pelo modelo) e MAPE (erro percentual médio). Além disso, o dashboard tem uma aba que compara **Previsto × Real** visualmente, permitindo validação por inspeção."

### "Por que usar PostgreSQL e não MongoDB?"

> "PostgreSQL porque os dados são **estruturados e relacionais** (indicadores com schema fixo). A capacidade de fazer **JOINs complexos** entre `indicadores_fundamentalistas`, `resultados_precos` e `recomendacoes_acoes` é crucial. Além disso, PostgreSQL oferece **ACID completo** para garantir consistência nos backups e **UPSERT** nativo para idempotência."

### "Como o sistema lida com caminhos com espaços no Windows?"

> "Inicialmente tive problemas com `docker cp` em caminhos como 'Google Drive'. Resolvi usando **stdin/stdout streaming** no backup, passando o arquivo diretamente via pipe em vez de copiar para o container. Isso é mais robusto, rápido e multiplataforma."

### "Quais são os próximos passos do projeto?"

**Curto Prazo:**
1. Incorporar **análise técnica** (RSI, MACD, Bollinger Bands)
2. Implementar **SHAP values** para explicabilidade por predição
3. Adicionar **testes automatizados** (pytest)

**Médio Prazo:**
4. **Análise de sentimento** via NLP em notícias financeiras
5. **Backtesting** de estratégias de compra/venda
6. **API REST** com FastAPI

**Longo Prazo:**
7. **Transfer Learning** de modelos financeiros pré-treinados
8. Expansão para outras bolsas (NASDAQ, NYSE)

---

## Pontos Fortes para Destacar

### ✅ Rigor Científico
- Validação temporal correta
- Hold-out independente do CV
- Métricas adequadas

### ✅ Engenharia de Software
- Arquitetura escalável
- Paralelismo em múltiplas camadas
- Docker para portabilidade
- Idempotência garantida

### ✅ Resolução de Problemas
- 7 problemas identificados e documentados
- Evolução iterativa baseada em análise crítica
- Documentação clara do processo

### ✅ UX/UI
- Dashboard responsivo
- Barra de progresso em tempo real
- Visualizações interativas

### ✅ Automação
- Pipeline end-to-end
- Orquestração diária
- Backups automáticos

---

## Dicas para a Apresentação

### ✅ DO
- Mostrar **código real** (especialmente merge_asof, TimeSeriesSplit)
- Demonstrar o **dashboard funcionando**
- Explicar **decisões de design** (por que escolheu X em vez de Y)
- Mencionar **métricas concretas** (não só "funciona bem")
- Conectar com **conceitos de negócio** (Value Investing, data leakage)

### ❌ DON'T
- Não dizer "é complexo" sem explicar
- Não focar só em tecnologias (mostrar **resultados**)
- Não exagerar nas métricas (seja honesto sobre limitações)
- Não ignorar perguntas difíceis (admita limitações e proponha soluções)

---

## Roteiro de Demonstração (5 min)

### Minuto 1: Conectar DBeaver
```sql
-- Mostrar dados reais
SELECT * FROM indicadores_fundamentalistas
WHERE acao = 'PETR4'
ORDER BY data_coleta DESC
LIMIT 5;
```

### Minuto 2: Abrir Dashboard - Aba Indicadores
- Selecionar "Desconto vs Graham"
- Apontar Top-10 ações subavaliadas
- Mostrar KPIs (R², MAPE)

### Minuto 3: Aba Previsões
- Digitar "VALE3" + "7 dias"
- Clicar "Carregar"
- Mostrar barra de progresso
- Explicar tabela de resultados

### Minuto 4: Aba Recomendador
- Digitar "ITUB4"
- Clicar "Recomendar"
- Explicar parecer:
  - Probabilidades
  - Pontos positivos/negativos
  - Filtros de sanidade

### Minuto 5: Mostrar Código
- Abrir `classificador.py` → mostrar TimeSeriesSplit
- Abrir `regressor_preco.py` → mostrar merge_asof
- Abrir `recomendador_acoes.py` → mostrar filtros de sanidade

---

## Mensagem Final

> "Este projeto demonstra minha capacidade de integrar múltiplas tecnologias (ML, banco de dados, web scraping, visualização) para resolver um problema real de forma end-to-end. Mais importante, mostra meu processo de **pensamento crítico** e **resolução iterativa de problemas**, documentando cada desafio enfrentado e como foi resolvido com base em princípios sólidos de Machine Learning e Value Investing."

**Boa sorte na entrevista! 🚀**