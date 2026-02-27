# 📚 Documentação INSIGHT-INVEST

Bem-vindo à documentação completa do sistema INSIGHT-INVEST!

---

## 📖 Índice de Documentos

### 🏗️ [ARQUITETURA.md](ARQUITETURA.md)
Visão técnica completa da arquitetura do sistema:
- Diagrama de arquitetura
- Fluxo de dados entre componentes
- Decisões de design
- Stack tecnológico
- Métricas de performance
- Volumes de dados

**Leia se você quer:** Entender como o sistema funciona internamente e por que foi construído dessa forma.

---

### 🚀 [INSTALACAO.md](INSTALACAO.md)
Guia passo a passo para instalar e executar o sistema:
- Instalação com Docker (recomendado)
- Instalação local (sem Docker)
- Configuração do DBeaver
- Comandos úteis
- Troubleshooting comum

**Leia se você quer:** Colocar o sistema para rodar na sua máquina.

---

### 🤖 [MACHINE_LEARNING.md](MACHINE_LEARNING.md)
Detalhamento técnico dos modelos de ML:
- Classificador de desempenho futuro
- Regressor de preços
- Rotulagem baseada em desempenho
- Feature engineering
- Validação temporal rigorosa
- Hyperparameter tuning
- Justificativas heurísticas

**Leia se você quer:** Entender profundamente os algoritmos, técnicas de ML e como evitamos data leakage.

---

### 🎯 [APRESENTACAO_ENTREVISTA.md](APRESENTACAO_ENTREVISTA.md)
Guia completo para apresentar o projeto em entrevistas:
- Elevator pitch (30 segundos)
- Estrutura de apresentação (10-15 min)
- Desafios técnicos resolvidos
- Perguntas frequentes e respostas prontas
- Roteiro de demonstração
- Dicas do que fazer e não fazer

**Leia se você vai:** Apresentar o projeto em processo seletivo, defesa de TCC ou entrevista técnica.

---

## 🗂️ Estrutura da Documentação

```
docs/
├── README.md (você está aqui)
├── ARQUITETURA.md (visão técnica)
├── INSTALACAO.md (setup e troubleshooting)
├── MACHINE_LEARNING.md (detalhes dos modelos)
└── APRESENTACAO_ENTREVISTA.md (guia para entrevistas)
```

---

## 🚦 Por Onde Começar?

### Se você é NOVO no projeto:
1. ✅ Leia [ARQUITETURA.md](ARQUITETURA.md) para entender o sistema
2. ✅ Siga [INSTALACAO.md](INSTALACAO.md) para rodar localmente
3. ✅ Explore o dashboard em http://localhost:8050
4. ✅ Leia [MACHINE_LEARNING.md](MACHINE_LEARNING.md) para detalhes técnicos

### Se você vai APRESENTAR o projeto:
1. ✅ Leia [APRESENTACAO_ENTREVISTA.md](APRESENTACAO_ENTREVISTA.md)
2. ✅ Pratique o elevator pitch (30 segundos)
3. ✅ Prepare demonstração prática (5 minutos)
4. ✅ Revise perguntas frequentes

### Se você está DESENVOLVENDO:
1. ✅ [ARQUITETURA.md](ARQUITETURA.md) → Entenda as decisões de design
2. ✅ [MACHINE_LEARNING.md](MACHINE_LEARNING.md) → Entenda os modelos
3. ✅ Código-fonte em `app/`

---

## 📊 Visão Rápida do Sistema

### O que o sistema faz?

1. **Coleta** 31 indicadores fundamentalistas de 149 ações da B3 (diariamente)
2. **Treina** modelos de Machine Learning para classificar e prever preços
3. **Gera** recomendações automatizadas com justificativas
4. **Apresenta** tudo em um dashboard interativo
5. **Orquestra** tarefas diárias e faz backup automático

### Principais Tecnologias

- **Backend:** Python 3.12
- **ML:** scikit-learn (RandomForest)
- **Banco:** PostgreSQL 15
- **Dashboard:** Dash/Plotly
- **Container:** Docker + docker-compose

### Números-chave

- 149 tickers coletados
- 31 indicadores por ação
- ~134k registros históricos
- 7-12 minutos de execução diária
- 65-75% de acurácia no classificador
- 0.85-0.95 de R² no regressor

---

## 🔗 Links Úteis

### Projeto
- **Dashboard:** http://localhost:8050 (após iniciar)
- **DBeaver:** localhost:5432, database: stocks, user: user, password: password

### Arquivos Principais
- **Scraper:** `app/scraper_indicadores.py`
- **Classificador:** `app/classificador.py`
- **Regressor:** `app/regressor_preco.py`
- **Recomendador:** `app/recomendador_acoes.py`
- **Dashboard:** `app/dashboard/app.py`
- **Orquestrador:** `app/executar_tarefas_diarias.py`

### Backup
- **Script:** `app/backup.py`
- **Pasta:** `app/backups/`

---

## 🛟 Precisa de Ajuda?

### Problemas Comuns

**Docker não sobe:**
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

**Banco não conecta:**
```bash
docker compose ps  # Verificar se está rodando
docker compose logs db  # Ver logs
```

**Dashboard não abre:**
```bash
netstat -ano | findstr :8050  # Ver se porta está em uso
```

Mais detalhes em [INSTALACAO.md](INSTALACAO.md) seção "Troubleshooting"

---

## 🤝 Contribuindo

Este é um projeto de TCC, mas sugestões são bem-vindas!

### Melhorias Futuras Planejadas

- [ ] Análise técnica (RSI, MACD)
- [ ] SHAP values para interpretabilidade
- [ ] Testes automatizados (pytest)
- [ ] Análise de sentimento (NLP)
- [ ] API REST (FastAPI)
- [ ] Backtesting de estratégias

---

## 📄 Licença

Projeto acadêmico - TCC de Ciência da Computação

---

## 👤 Autor

**Mateus Restier**
- TCC: Sistema Automatizado de Análise, Previsão e Recomendação de Ações com Visual Analytics
- Ano: 2024-2025

---

**Última atualização:** 2025-02-19