import os
import requests
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from src.data.scraper_orquestrador import coletar_com_fallback as coletar_indicadores

# -----------------------------------------------------------------------------
# Agrupamento semântico dos indicadores
# -----------------------------------------------------------------------------
_INDICATOR_GROUPS = {
    "Valuation": [
        "pl", "psr", "pvp",
        "ev_ebitda", "valor_firma_ebitda",   # ambos os nomes possíveis do scraper
        "ev_ebit",  "valor_firma_ebit",
        "p_ebitda", "p_ebit",
        "p_ativo",  "p_cap_giro", "p_ativo_circ_liq",
        "lpa", "vpa", "cotacao",
    ],
    "Rentabilidade": [
        "margem_liquida", "margem_bruta", "margem_ebit", "margem_ebitda",
        "roe", "roic", "roa",
    ],
    "Dividendos": [
        "dividend_yield", "dy", "payout",   # ambos os nomes possíveis para DY
    ],
    "Endividamento": [
        "div_liq_patrimonio", "div_liq_ebitda", "div_liq_ebit", "div_bruta_patrimonio",
        "patrimonio_ativos", "passivos_ativos",
    ],
    "Liquidez & Crescimento": [
        "giro_ativos", "liquidez_corrente", "variacao_12m",
    ],
}

_DISPLAY_NAMES = {
    "acao": "Ação",
    # Valuation
    "pl": "P/L", "psr": "P/SR", "pvp": "P/VP",
    "ev_ebitda": "EV/EBITDA", "valor_firma_ebitda": "EV/EBITDA",
    "ev_ebit":   "EV/EBIT",   "valor_firma_ebit":   "EV/EBIT",
    "p_ebitda": "P/EBITDA", "p_ebit": "P/EBIT",
    "p_ativo": "P/Ativo", "p_cap_giro": "P/Cap. Giro",
    "p_ativo_circ_liq": "P/Ativo Circ. Líq.",
    "lpa": "LPA", "vpa": "VPA", "cotacao": "Cotação (R$)",
    # Rentabilidade
    "margem_liquida": "Margem Líquida", "margem_bruta": "Margem Bruta",
    "margem_ebit": "Margem EBIT", "margem_ebitda": "Margem EBITDA",
    "roe": "ROE", "roic": "ROIC", "roa": "ROA",
    # Dividendos
    "dividend_yield": "Dividend Yield", "dy": "Dividend Yield", "payout": "Payout",
    # Endividamento
    "div_liq_patrimonio": "Dív. Líq./Patrimônio", "div_liq_ebitda": "Dív. Líq./EBITDA",
    "div_liq_ebit": "Dív. Líq./EBIT", "div_bruta_patrimonio": "Dív. Bruta/Patrimônio",
    "patrimonio_ativos": "Patrimônio/Ativos", "passivos_ativos": "Passivos/Ativos",
    # Liquidez & Crescimento
    "giro_ativos": "Giro Ativos", "liquidez_corrente": "Liquidez Corrente",
    "variacao_12m": "Variação 12M",
}

# Campos cujo valor é exibido com "%"
_PERCENT_KEYS = {
    "dy", "dividend_yield", "payout",
    "margem_liquida", "margem_bruta", "margem_ebit", "margem_ebitda",
    "roe", "roic", "roa", "variacao_12m",
}

# Campos onde positivo = bom → cor verde; negativo = ruim → cor vermelha
_SIGNED_KEYS = {
    "dy", "dividend_yield",
    "margem_liquida", "margem_bruta", "margem_ebit", "margem_ebitda",
    "roe", "roic", "roa", "variacao_12m",
}

# Indicadores básicos exibidos em destaque no topo (em ordem de exibição).
# "dy"/"dividend_yield" são o mesmo campo com nomes diferentes — tratado na lógica.
_HIGHLIGHT_KEYS = ["cotacao", "pl", "pvp", "dividend_yield", "dy", "roe", "variacao_12m"]

_INDICADORES_CHAVE_NAMES = {
    "dividend_yield": "Dividend Yield",
    "roe": "ROE",
    "variacao_12m": "Variação 12M",
    "margem_liquida": "Margem Líquida",
}


# -----------------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------------
def layout_recomendador():
    return dbc.Row([
        # Coluna da Esquerda: Card de Recomendação
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📝 Recomendador de Ações"),
                dbc.CardBody([
                    html.Div([
                        dbc.Input(
                            id="input-ticker-rec",
                            value="BBAS3",
                            type="text",
                            placeholder="Ex: ITUB4",
                            className="input-dark",
                            style={"width": "150px", "marginRight": "10px"}
                        ),
                        dbc.Button(
                            "Recomendar",
                            id="btn-recommend",
                            className="btn-botaoacao"
                        )
                    ], className="mb-3 d-flex align-items-center"),

                    html.Div(
                        dcc.Loading(
                            id="loading-recommendation",
                            type="circle",
                            children=html.Div(
                                id="recomendation-output",
                                children=html.P(
                                    "Informe um ticker e clique em Recomendar para ver o relatório.",
                                    className="text-muted small mt-2"
                                ),
                            )
                        ),
                        className="flex-grow-1"
                    )
                ], className="d-flex flex-column"),
            ], className="shadow-sm mb-4 h-100"),
        ], md=5),

        # Coluna da Direita: Indicadores da Ação
        dbc.Col([
            html.H5("🪄 Indicadores da Ação Selecionada:", className="mb-2"),
            dcc.Loading(
                id="loading-cards-rec",
                type="circle",
                children=html.Div(
                    id="cards-indicadores-rec",
                    style={"marginTop": "0.5rem"},
                    children=html.P(
                        "Os indicadores fundamentalistas da ação aparecerão aqui.",
                        className="text-muted small"
                    ),
                )
            ),
        ], md=7),
    ], className="align-items-stretch")


# -----------------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------------
def register_callbacks_recomendador(app):
    def _resolver_api_url():
        api_url = os.getenv("API_URL", "").rstrip("/")
        if api_url:
            return api_url
        porta = os.getenv("PORT", "8000")
        return f"http://127.0.0.1:{porta}"

    @app.callback(
        Output("cards-indicadores-rec", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value"),
    )
    def update_indicators(n_clicks, ticker):
        if not n_clicks or not ticker:
            return html.P("Insira um ticker e clique em Recomendar.", className="text-muted small")

        resultado = coletar_indicadores(ticker)
        if isinstance(resultado, str):
            return dbc.Alert(resultado, color="danger", dismissable=True)
        if isinstance(resultado, tuple) and len(resultado) >= 1:
            dados = resultado[0]
        elif isinstance(resultado, dict):
            dados = resultado
        else:
            return dbc.Alert(
                "Falha ao interpretar dados coletados para o ticker.",
                color="danger",
                dismissable=True,
            )

        def _fmt(nome, valor):
            if valor is None:
                return "–"
            if isinstance(valor, (int, float)):
                return f"{valor:.2f}%" if nome in _PERCENT_KEYS else f"{valor:.2f}"
            return str(valor)

        def _valor_color(nome, valor):
            """Verde se campo assinado com valor positivo, vermelho se negativo."""
            if nome not in _SIGNED_KEYS or not isinstance(valor, (int, float)):
                return "#e0e0e0"
            return "#00cc96" if valor > 0 else "#ff6b6b"

        def _make_card(nome, valor):
            label = _DISPLAY_NAMES.get(nome, nome.replace("_", " ").title())
            return dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.P(label, className="card-title mb-1",
                               style={"fontSize": "0.78rem", "color": "#9b9bb5"}),
                        html.H6(_fmt(nome, valor), className="card-text mb-0 fw-bold",
                                style={"color": _valor_color(nome, valor),
                                       "fontFamily": "'Courier New', Courier, monospace",
                                       "fontSize": "1rem"}),
                    ]),
                    className="h-100 shadow-sm",
                ),
                xs=6, sm=4, md=4, lg=3,
                className="mb-3",
            )

        def _make_highlight_card(nome, valor):
            """Card maior para os indicadores básicos em destaque."""
            label = _DISPLAY_NAMES.get(nome, nome.replace("_", " ").title())
            color = _valor_color(nome, valor)
            return dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.P(label, className="mb-1", style={
                            "fontSize": "0.7rem", "color": "#9b9bb5",
                            "textTransform": "uppercase", "letterSpacing": "0.06em",
                        }),
                        html.H4(_fmt(nome, valor), className="mb-0 fw-bold", style={
                            "color": color,
                            "fontFamily": "'Courier New', Courier, monospace",
                            "fontSize": "1.3rem",
                        }),
                    ], style={"padding": "14px 16px"}),
                    style={
                        "backgroundColor": "#2c2c3e",
                        "border": "1px solid rgba(85, 97, 255, 0.3)",
                        "borderRadius": "8px",
                    },
                ),
                xs=6, sm=4, md=2,
                className="mb-2",
            )

        # --- Seção de destaques (indicadores básicos) ---
        # dy e dividend_yield são o mesmo campo com nomes diferentes — evita duplicata
        highlight_cards = []
        dy_seen = False
        for k in _HIGHLIGHT_KEYS:
            if k in ("dy", "dividend_yield"):
                if dy_seen:
                    continue
                dy_seen = True
            if k in dados:
                highlight_cards.append(_make_highlight_card(k, dados[k]))

        groups = []
        if highlight_cards:
            groups.append(html.Div([
                html.P("Destaques", className="mb-2 mt-1", style={
                    "color": "#b0b8ff", "fontSize": "0.7rem",
                    "textTransform": "uppercase", "letterSpacing": "0.08em",
                    "borderBottom": "1px solid #5561ff", "paddingBottom": "4px",
                }),
                dbc.Row(highlight_cards, className="g-2"),
            ], className="mb-4"))

        seen = set()
        for group_name, keys in _INDICATOR_GROUPS.items():
            group_cards = [_make_card(k, dados[k]) for k in keys if k in dados]
            if not group_cards:
                continue
            seen.update(k for k in keys if k in dados)
            groups.append(html.Div([
                html.P(
                    group_name,
                    className="mb-2 mt-1",
                    style={"color": "#9b9bb5", "fontSize": "0.7rem",
                           "textTransform": "uppercase", "letterSpacing": "0.06em",
                           "borderBottom": "1px solid #3a3a50", "paddingBottom": "4px"}
                ),
                dbc.Row(group_cards, className="g-2"),
            ], className="mb-3"))

        # Campos extras não cobertos pelos grupos
        extras = [_make_card(k, v) for k, v in dados.items()
                  if k not in seen and k != "acao"]
        if extras:
            groups.append(html.Div([
                html.P("Outros", className="mb-2 mt-1",
                       style={"color": "#9b9bb5", "fontSize": "0.7rem",
                              "textTransform": "uppercase", "letterSpacing": "0.06em",
                              "borderBottom": "1px solid #3a3a50", "paddingBottom": "4px"}),
                dbc.Row(extras, className="g-2"),
            ], className="mb-3"))

        return groups

    @app.callback(
        Output("recomendation-output", "children"),
        Input("btn-recommend", "n_clicks"),
        State("input-ticker-rec", "value"),
    )
    def update_recommend(n_clicks, ticker):
        if not n_clicks:
            return no_update

        api_url = _resolver_api_url()
        api_key = os.getenv("API_KEY", "")

        if not api_key:
            return dbc.Alert("Configuração ausente: defina API_KEY no serviço.", color="warning")

        if not ticker:
            return dbc.Alert("Informe um ticker válido.", color="warning")

        try:
            resp = requests.post(
                f"{api_url}/recomendacao/{ticker.strip().upper()}",
                headers={"X-API-Key": api_key},
                timeout=45,
            )
        except requests.RequestException as exc:
            return dbc.Alert(f"Falha ao chamar API de recomendação: {exc}", color="danger")

        if resp.status_code != 200:
            try:
                detalhe = resp.json().get("detail", resp.text)
            except Exception:
                detalhe = resp.text
            return dbc.Alert(f"Erro da API ({resp.status_code}): {detalhe}", color="danger")

        payload = resp.json()
        prob     = payload.get("probabilidades", {})
        prob_nao = float(prob.get("nao_recomendada", 0.0))
        prob_sim = float(prob.get("recomendada", 0.0))
        resultado    = payload.get("resultado", "Sem resultado")
        ticker_resp  = payload.get("ticker", ticker).upper()
        indicadores_chave      = payload.get("indicadores_chave", {})
        justificativas_positivas = payload.get("justificativas_positivas", [])
        justificativas_negativas = payload.get("justificativas_negativas", [])

        is_rec       = "NÃO" not in resultado
        alert_color  = "success" if is_rec else "danger"
        result_icon  = "✅" if is_rec else "❌"

        # --- Bloco de indicadores-chave ---
        _PERCENT_FEATS = {"dividend_yield", "roe", "variacao_12m", "margem_liquida"}
        indicadores_block = []
        if indicadores_chave:
            metric_rows = []
            for feat, val in indicadores_chave.items():
                nome = _INDICADORES_CHAVE_NAMES.get(feat, feat.replace("_", " ").title())
                if val is None:
                    val_str   = "N/D"
                    val_color = "#7a7a9a"
                elif feat in _PERCENT_FEATS:
                    val_str   = f"{val:.2f}%"
                    val_color = "#00cc96" if val > 0 else "#ff6b6b"
                else:
                    val_str   = f"{val:.2f}"
                    val_color = "#c8c8e0"

                metric_rows.append(
                    html.Div([
                        html.Span(nome, style={"color": "#9b9bb5", "fontSize": "0.8rem"}),
                        html.Span(val_str, style={
                            "color": val_color,
                            "fontWeight": "700",
                            "fontFamily": "'Courier New', Courier, monospace",
                            "fontSize": "0.85rem",
                        }),
                    ], style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                        "padding": "6px 0",
                        "borderBottom": "1px solid #2a2a3e",
                    })
                )

            indicadores_block = [
                html.Div([
                    html.P("Indicadores-chave", style={
                        "color": "#9b9bb5", "textTransform": "uppercase",
                        "fontSize": "0.68rem", "letterSpacing": "0.08em",
                        "marginBottom": "8px", "fontWeight": "600",
                    }),
                    *metric_rows,
                ], style={
                    "backgroundColor": "#2c2c3e",
                    "borderRadius": "6px",
                    "padding": "12px 14px",
                    "marginTop": "10px",
                })
            ]

        # --- Pontos positivos ---
        positivos_card = []
        if justificativas_positivas:
            positivos_card = [
                html.Div([
                    html.Div([
                        html.Span("Pontos Positivos", style={
                            "color": "#00cc96", "fontWeight": "700",
                            "fontSize": "0.78rem", "textTransform": "uppercase",
                            "letterSpacing": "0.06em",
                        }),
                    ], style={"marginBottom": "8px"}),
                    html.Ul([
                        html.Li(item, style={
                            "color": "#c8c8e0", "fontSize": "0.82rem",
                            "padding": "3px 0", "lineHeight": "1.5",
                        })
                        for item in justificativas_positivas
                    ], style={"listStyle": "disc", "paddingLeft": "16px", "marginBottom": "0"}),
                ], style={
                    "backgroundColor": "#162820",
                    "border": "1px solid rgba(0, 204, 150, 0.2)",
                    "borderLeft": "3px solid #00cc96",
                    "borderRadius": "6px",
                    "padding": "12px 14px",
                    "marginTop": "8px",
                })
            ]

        # --- Pontos de atenção ---
        negativos_card = []
        if justificativas_negativas:
            negativos_card = [
                html.Div([
                    html.Div([
                        html.Span("Pontos de Atenção", style={
                            "color": "#f59e0b", "fontWeight": "700",
                            "fontSize": "0.78rem", "textTransform": "uppercase",
                            "letterSpacing": "0.06em",
                        }),
                    ], style={"marginBottom": "8px"}),
                    html.Ul([
                        html.Li(item, style={
                            "color": "#c8c8e0", "fontSize": "0.82rem",
                            "padding": "3px 0", "lineHeight": "1.5",
                        })
                        for item in justificativas_negativas
                    ], style={"listStyle": "disc", "paddingLeft": "16px", "marginBottom": "0"}),
                ], style={
                    "backgroundColor": "#231c0e",
                    "border": "1px solid rgba(245, 158, 11, 0.2)",
                    "borderLeft": "3px solid #f59e0b",
                    "borderRadius": "6px",
                    "padding": "12px 14px",
                    "marginTop": "8px",
                })
            ]

        # --- Gauge visual ---
        gauge_bar_color = "#00cc96" if is_rec else "#ff6b6b"
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(prob_sim * 100, 1),
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickcolor": "#9b9bb5",
                    "tickfont": {"color": "#9b9bb5", "size": 10},
                },
                "bar": {"color": gauge_bar_color, "thickness": 0.25},
                "bgcolor": "#252535",
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  50], "color": "#3d2020"},
                    {"range": [50, 100], "color": "#1a3d2c"},
                ],
                "threshold": {
                    "line": {"color": "#9b9bb5", "width": 1},
                    "thickness": 0.75,
                    "value": 50,
                },
            },
            number={"suffix": "%", "font": {"color": "#e0e0e0", "size": 30}},
            title={"text": "Prob. Recomendada", "font": {"color": "#9b9bb5", "size": 11}},
        ))
        gauge_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=190,
            margin=dict(l=20, r=20, t=35, b=5),
        )

        return html.Div([
            # Veredicto
            dbc.Alert([
                html.H5(f"{result_icon} {ticker_resp}", className="alert-heading mb-1"),
                html.P(resultado, className="mb-0 fw-bold"),
            ], color=alert_color, className="mb-2"),

            # Gauge
            dcc.Graph(figure=gauge_fig, config={"displayModeBar": False}),

            # Indicadores-chave, pontos positivos e pontos de atenção
            *indicadores_block,
            *positivos_card,
            *negativos_card,
        ])
