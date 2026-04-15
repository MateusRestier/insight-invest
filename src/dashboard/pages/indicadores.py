
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from dash import dash_table
from dash.dash_table.Format import Format, Scheme, Sign

from src.core.db_connection import get_connection

# ----------------------------------------------------------------------
# Layout da página "Indicadores"
# ----------------------------------------------------------------------
def layout_indicadores():
    performance_cards = [
        dbc.Card(
            dbc.CardBody([
                html.P("MAE", className="metric-label mb-1"),
                html.H4(id="card-mae", className="metric-value mb-0"),
            ]),
            id="card-mae-container",
            className="performance-card",
        ),
        dbc.Card(
            dbc.CardBody([
                html.P("MSE", className="metric-label mb-1"),
                html.H4(id="card-mse", className="metric-value mb-0"),
            ]),
            id="card-mse-container",
            className="performance-card",
        ),
        dbc.Card(
            dbc.CardBody([
                html.P("RMSE", className="metric-label mb-1"),
                html.H4(id="card-rmse", className="metric-value mb-0"),
            ]),
            id="card-rmse-container",
            className="performance-card",
        ),
        dbc.Card(
            dbc.CardBody([
                html.P("R²", className="metric-label mb-1"),
                html.H4(id="card-r2", className="metric-value mb-0"),
            ]),
            id="card-r2-container",
            className="performance-card",
        ),
        dbc.Card(
            dbc.CardBody([
                html.P("MAPE", className="metric-label mb-1"),
                html.H4(id="card-mape", className="metric-value mb-0"),
            ]),
            id="card-mape-container",
            className="performance-card",
        ),
    ]

    return dbc.Container(fluid=True, children=[
        html.H4("Indicadores Fundamentalistas", className="mb-4 fw-bold"),

        # ── SEÇÃO 1: RANKING ────────────────────────────────────────────
        dbc.Card([
            dbc.CardHeader(
                dbc.Row([
                    dbc.Col(
                        html.Span("📊 Ranking por Métrica", className="fw-semibold"),
                        width="auto", className="d-flex align-items-center"
                    ),
                    dbc.Col(
                        dbc.Select(
                            id="metric-picker",
                            value="graham",
                            options=[
                                {"label": "Top 10 — Maior desconto segundo Graham (P/L e ROE positivos)", "value": "graham"},
                                {"label": "Top 10 — Maior Dividend Yield (P/L e ROE positivos)",          "value": "dividend_yield"},
                                {"label": "Top 10 — Maior ROE (P/L e LPA positivos)",                     "value": "roe"},
                                {"label": "Top 10 — Cotação mais alta",                                    "value": "cotacao"},
                                {"label": "Top 10 — Maior Margem Líquida (%)",                            "value": "margem_liquida"},
                                {"label": "Top 10 — Menor Dívida Líq./Patrimônio",                        "value": "div_liq_patrimonio"},
                            ],
                            className="dropdown-dark",
                            style={"color": "#e0e0e0", "backgroundColor": "#1e1e2f", "borderColor": "#444"}
                        ),
                        xs=12, md=8
                    ),
                ], align="center", className="g-2"),
            ),
            dbc.CardBody(
                dbc.Row([
                    dbc.Col(dcc.Graph(id="grafico-top-metric"), xs=12, md=8),
                    dbc.Col(
                        html.Div(
                            id="cards-top10-recs",
                            style={"maxHeight": "450px", "overflowY": "auto", "padding": "0 0.5rem"}
                        ),
                        xs=12, md=4
                    ),
                ]),
            ),
        ], className="mb-4"),

        # ── SEÇÃO 2: COMPARAÇÃO PREVISTO × REAL ─────────────────────────
        dbc.Card([
            dbc.CardHeader([
                html.Span("📈 Comparação Preço Previsto × Real", className="fw-semibold d-block"),
                html.Span(
                    "Cada linha é uma previsão do modelo: o preço estimado para uma data futura vs. a cotação real registrada naquele dia.",
                    className="text-muted fw-normal d-block",
                    style={"fontSize": "0.78rem", "marginTop": "2px"},
                ),
            ]),
            dbc.CardBody([

                # Filtros — flex puro garante 4 colunas iguais sem overflow
                html.Div([
                    html.Div([
                        dbc.Label("Data Alvo", html_for="filter-data-previsao", className="text-muted small mb-1"),
                        dbc.Input(id="filter-data-previsao", type="date", className="input-dark"),
                    ], className="filter-col"),
                    html.Div([
                        dbc.Label("Gerada em", html_for="filter-data-calculo", className="text-muted small mb-1"),
                        dbc.Input(id="filter-data-calculo", type="date", className="input-dark"),
                    ], className="filter-col"),
                    html.Div([
                        dbc.Label("Ação", html_for="filter-acao-ind", className="text-muted small mb-1"),
                        dcc.Dropdown(
                            id='filter-acao-ind', options=[], placeholder='Selecione Ação',
                            clearable=True, searchable=True, className='dropdown-dark',
                            style={"backgroundColor": "#1e1e2f", "color": "#e0e0e0", "borderColor": "#444"}
                        ),
                    ], className="filter-col"),
                    html.Div([
                        dbc.Label("Erro %", html_for="filter-erro-pct", className="text-muted small mb-1"),
                        dcc.Dropdown(
                            id='filter-erro-pct',
                            options=[
                                {'label': 'Maior que 0', 'value': 'gt0'},
                                {'label': 'Menor que 0', 'value': 'lt0'},
                                {'label': 'Igual a 0',   'value': 'eq0'},
                            ],
                            placeholder='Selecione', multi=True, className='dropdown-dark',
                            style={"backgroundColor": "#1e1e2f", "color": "#e0e0e0", "borderColor": "#444"}
                        ),
                    ], className="filter-col"),
                ], className="filtros-indicadores mb-4"),

                # Performance do modelo
                html.Div(
                    performance_cards,
                    className="performance-cards-row g-2 mb-3",
                    style={"width": "100%", "margin": "0"}
                ),

                # Legenda de cores da coluna Erro %
                html.Div([
                    html.Span("Erro %:", className="text-muted small me-2", style={"fontSize": "0.75rem"}),
                    html.Span("● Preciso", style={"color": "#00cc96", "fontSize": "0.75rem", "marginRight": "12px"}),
                    html.Span("● Errou pra mais", style={"color": "#60a5fa", "fontSize": "0.75rem", "marginRight": "12px"}),
                    html.Span("● Errou pra menos", style={"color": "#a78bfa", "fontSize": "0.75rem"}),
                ], className="mb-2", style={"display": "flex", "flexWrap": "wrap", "alignItems": "center", "gap": "2px"}),

                # Tooltips para métricas
                dbc.Tooltip("MAE (Mean Absolute Error): média dos erros absolutos entre preços previstos e reais.", target="card-mae-container", placement="top"),
                dbc.Tooltip("MSE (Mean Squared Error): média dos quadrados dos erros entre preços previstos e reais.", target="card-mse-container", placement="top"),
                dbc.Tooltip("RMSE (Root Mean Squared Error): raiz do MSE, erro médio em unidades de preço.", target="card-rmse-container", placement="top"),
                dbc.Tooltip("R² (Coeficiente de Determinação): proporção da variância do preço real explicada pelo modelo.", target="card-r2-container", placement="top"),
                dbc.Tooltip("MAPE (Mean Absolute Percentage Error): erro percentual médio absoluto.", target="card-mape-container", placement="top"),

                # Tabela + pizza com loading
                dcc.Loading(
                    type="dot",
                    color="#5561ff",
                    children=dbc.Row([
                        dbc.Col(
                            html.Div(
                                dash_table.DataTable(
                                    id="table-previsto-real",
                                    page_size=10,
                                    sort_action="native",
                                    # ── Estrutura geral ──
                                    style_table={
                                        "minWidth": "100%",
                                        "borderRadius": "8px",
                                        "overflow": "hidden",
                                        "border": "1px solid #2a2a3e",
                                    },
                                    # ── Header ──
                                    style_header={
                                        "backgroundColor": "#2a2a45",
                                        "color": "#e8e8ff",
                                        "fontWeight": "700",
                                        "textAlign": "center",
                                        "textTransform": "uppercase",
                                        "fontSize": "0.7rem",
                                        "letterSpacing": "0.08em",
                                        "borderBottom": "1px solid #5561ff",
                                        "borderTop": "none",
                                        "borderLeft": "none",
                                        "borderRight": "none",
                                        "padding": "12px 14px",
                                    },
                                    # ── Células base ──
                                    style_cell={
                                        "backgroundColor": "#1e1e2f",
                                        "color": "#d0d0e8",
                                        "textAlign": "center",
                                        "padding": "11px 14px",
                                        "whiteSpace": "normal",
                                        "height": "auto",
                                        "border": "none",
                                        "borderBottom": "1px solid #2a2a3e",
                                        "fontSize": "0.86rem",
                                    },
                                    # ── Células condicionais por coluna ──
                                    style_cell_conditional=[
                                        # Ação: à esquerda, cor de destaque
                                        {
                                            "if": {"column_id": "acao"},
                                            "textAlign": "left",
                                            "fontWeight": "700",
                                            "color": "#b0b8ff",
                                            "paddingLeft": "18px",
                                            "minWidth": "72px",
                                        },
                                        # Valores monetários: direita, monospace
                                        {
                                            "if": {"column_id": ["preco_previsto", "preco_real"]},
                                            "textAlign": "right",
                                            "fontFamily": "'Courier New', Courier, monospace",
                                            "paddingRight": "20px",
                                            "color": "#c8c8e0",
                                        },
                                        # Erro %: direita, monospace, padding extra
                                        {
                                            "if": {"column_id": "erro_pct"},
                                            "textAlign": "right",
                                            "fontFamily": "'Courier New', Courier, monospace",
                                            "paddingRight": "20px",
                                            "fontWeight": "600",
                                        },
                                        # Datas: centralizadas, tom secundário
                                        {
                                            "if": {"column_id": ["data_calculo", "data_previsao"]},
                                            "fontSize": "0.8rem",
                                            "color": "#7a7a9a",
                                        },
                                        # Oculta coluna auxiliar de cor
                                        {
                                            "if": {"column_id": "_cor_erro"},
                                            "display": "none",
                                            "width": "0px",
                                            "minWidth": "0px",
                                            "maxWidth": "0px",
                                            "padding": "0px",
                                        },
                                    ],
                                    # ── Header condicional: oculta coluna auxiliar ──
                                    style_header_conditional=[
                                        {
                                            "if": {"column_id": "_cor_erro"},
                                            "display": "none",
                                            "width": "0px",
                                            "minWidth": "0px",
                                            "maxWidth": "0px",
                                            "padding": "0px",
                                        },
                                    ],
                                    # ── Dados condicionais ──
                                    style_data_conditional=[
                                        # Linhas alternadas muito sutis
                                        {
                                            "if": {"row_index": "odd"},
                                            "backgroundColor": "#232336",
                                        },
                                        # Seleção
                                        {
                                            "if": {"state": "selected"},
                                            "backgroundColor": "rgba(85,97,255,0.25)",
                                            "color": "#ffffff",
                                            "border": "none",
                                        },
                                        # ── Cor do Erro % — 3 categorias de igual peso visual ──
                                        # pos/neg usam tons frios de mesma luminosidade:
                                        # nenhum "parece pior" que o outro, só direções opostas.
                                        {
                                            "if": {"filter_query": '{_cor_erro} = "pos"',  "column_id": "erro_pct"},
                                            "color": "#60a5fa",   # azul céu
                                        },
                                        {
                                            "if": {"filter_query": '{_cor_erro} = "neg"',  "column_id": "erro_pct"},
                                            "color": "#a78bfa",   # violeta suave
                                        },
                                        {
                                            "if": {"filter_query": '{_cor_erro} = "zero"', "column_id": "erro_pct"},
                                            "color": "#00cc96",   # verde — acerto preciso
                                            "fontWeight": "700",
                                        },
                                    ],
                                    # ── Tooltips nos headers ──
                                    tooltip_header={
                                        "data_calculo":   "Data em que o modelo calculou esta previsão",
                                        "data_previsao":  "Data futura para a qual o preço foi previsto",
                                        "preco_previsto": "Preço estimado pelo modelo (R$)",
                                        "preco_real":     "Cotação real registrada na data alvo (R$)",
                                        "erro_pct":       "Desvio percentual: (Previsto − Real) ÷ Real × 100",
                                    },
                                    tooltip_delay=300,
                                    tooltip_duration=None,
                                ),
                                className="table-responsive"
                            ),
                            xs=12, lg=8
                        ),
                        dbc.Col(
                            dcc.Graph(
                                id='pie-error-dist',
                                config={'displayModeBar': False},
                                style={'marginTop': '10px'},
                            ),
                            xs=12, lg=4
                        ),
                    ], className="align-items-start"),
                ),

            ]),
        ], className="mb-4"),
    ])


# ----------------------------------------------------------------------
# Callbacks da página "Indicadores"
# ----------------------------------------------------------------------
def register_callbacks_indicadores(app):
    @app.callback(
        Output("grafico-top-metric", "figure"),
        Input("metric-picker", "value")
    )
    def plotar_top_10(metrico):
        try:
            conn = get_connection()
            if metrico == "graham":
                query = """
                    SELECT acao, lpa, vpa, cotacao, pl, roe
                    FROM indicadores_fundamentalistas
                    WHERE data_coleta = (
                        SELECT MAX(data_coleta) FROM indicadores_fundamentalistas
                    )
                      AND lpa > 0 AND vpa > 0 AND cotacao > 0
                      AND pl >= 0 AND roe >= 0
                """
                df = pd.read_sql(query, conn)
                df[["lpa", "vpa", "cotacao"]] = df[["lpa", "vpa", "cotacao"]].apply(pd.to_numeric, errors='coerce')
                df = df.dropna(subset=['lpa', 'vpa', 'cotacao'])
                df['valor_graham'] = np.sqrt(22.5 * df['lpa'] * df['vpa'])
                df['metrica'] = df['valor_graham'] - df['cotacao']
                df = df[df['metrica'] > 0].sort_values('metrica', ascending=False).head(10)
                y_label = 'Desconto vs. Valor Graham'
            else:
                query = f"""
                    SELECT acao, {metrico} AS metrica
                    FROM indicadores_fundamentalistas
                    WHERE data_coleta = (
                        SELECT MAX(data_coleta) FROM indicadores_fundamentalistas
                    ) AND {metrico} IS NOT NULL
                """
                if metrico == 'dividend_yield':
                    query = query.replace('WHERE', 'WHERE pl >= 0 AND roe >= 0 AND')
                if metrico == 'roe':
                    query = query.replace('WHERE', 'WHERE pl >= 0 AND lpa > 0 AND')
                df = pd.read_sql(query, conn)
                df['metrica'] = pd.to_numeric(df['metrica'], errors='coerce')
                df = df.dropna(subset=['metrica'])
                if metrico == 'div_liq_patrimonio':
                    tmp = df.sort_values('metrica').head(10)
                    df = tmp.sort_values('metrica', ascending=False)
                else:
                    df = df.sort_values('metrica', ascending=False).head(10)
                labels = {
                    "dividend_yield": "Dividend Yield (%)",
                    "roe": "ROE (%)",
                    "cotacao": "Cotação (R$)",
                    "margem_liquida": "Margem Líquida (%)",
                    "div_liq_patrimonio": "Dív. Líq./Patrimônio"
                }
                y_label = labels.get(metrico, metrico)
            conn.close()

            if df.empty:
                return px.bar(title="Sem dados para este ranking no momento")

            fig = px.bar(
                df,
                x='acao', y='metrica', text='metrica',
                labels={'acao': '', 'metrica': y_label},
                category_orders={'acao': df['acao'].tolist()}
            )
            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                plot_bgcolor='#1e1e2f', paper_bgcolor='#1e1e2f',
                font=dict(color='#e0e0e0'),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.2)')
            )
            return fig

        except Exception as e:
            return px.bar(title=f"Erro ao gerar gráfico: {e}")

    @app.callback(
        Output('filter-acao-ind', 'options'),
        Input('metric-picker', 'value')
    )
    def populate_acao_options(_):
        df = _get_comparison_df()
        vals = df['acao'].unique()
        return [{'label': a, 'value': a} for a in sorted(vals)]

    @app.callback(
        Output('table-previsto-real', 'data'),
        Output('table-previsto-real', 'columns'),
        Input('filter-data-previsao', 'value'),
        Input('filter-data-calculo', 'value'),
        Input('filter-acao-ind', 'value'),
        Input('filter-erro-pct', 'value')
    )
    def update_table(data_prev, data_calc, acao_sel, erro_sel):
        df = _get_comparison_df()

        if data_prev:
            df = df[df['data_previsao'] == data_prev]
        if data_calc:
            df = df[df['data_calculo'] == data_calc]
        if acao_sel:
            df = df[df['acao'] == acao_sel]

        if erro_sel:
            masks = []
            if 'gt0' in erro_sel:
                masks.append(df['erro_pct'] > 0)
            if 'lt0' in erro_sel:
                masks.append(df['erro_pct'] < 0)
            if 'eq0' in erro_sel:
                masks.append(df['erro_pct'] == 0)
            df = df[np.logical_or.reduce(masks)]

        df = df.sort_values('data_previsao', ascending=True)

        # Pré-computa categoria de cor para o erro_pct (3 categorias).
        # Usar string no filter_query é 100% confiável — evita problemas
        # de comparação numérica quando Format() converte o valor antes do match.
        def _categoria_erro(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "none"
            if v == 0:  return "zero"
            if v > 0:   return "pos"
            return "neg"

        df["_cor_erro"] = df["erro_pct"].apply(_categoria_erro)

        data = df.to_dict('records')
        _fmt2 = Format(precision=2, scheme=Scheme.fixed)
        cols = [
            {"name": "Ação",            "id": "acao"},
            {"name": "Gerada em",       "id": "data_calculo"},
            {"name": "Data Alvo",       "id": "data_previsao"},
            {"name": "Previsto (R$)",   "id": "preco_previsto", "type": "numeric", "format": _fmt2},
            {"name": "Real (R$)",       "id": "preco_real",     "type": "numeric", "format": _fmt2},
            {"name": "Erro %",          "id": "erro_pct",       "type": "numeric",
             "format": Format(precision=2, scheme=Scheme.fixed, sign=Sign.positive)},
            {"name": "",                "id": "_cor_erro"},   # coluna auxiliar oculta
        ]
        return data, cols

    @app.callback(
        Output('pie-error-dist', 'figure'),
        Input('filter-data-previsao', 'value'),
        Input('filter-data-calculo', 'value'),
        Input('filter-acao-ind', 'value'),
        Input('filter-erro-pct', 'value'),
    )
    def plot_error_distribution(data_prev, data_calc, acao_sel, erro_sel):
        df = _get_comparison_df()

        if data_prev:
            df = df[df['data_previsao'] == data_prev]
        if data_calc:
            df = df[df['data_calculo'] == data_calc]
        if acao_sel:
            df = df[df['acao'] == acao_sel]
        if erro_sel:
            masks = []
            if 'gt0' in erro_sel:
                masks.append(df['erro_pct'] > 0)
            if 'lt0' in erro_sel:
                masks.append(df['erro_pct'] < 0)
            if 'eq0' in erro_sel:
                masks.append(df['erro_pct'] == 0)
            df = df[np.logical_or.reduce(masks)]

        counts = {
            'Preciso':         int((df['erro_pct'] == 0).sum()),
            'Errou pra mais':  int((df['erro_pct'] > 0).sum()),
            'Errou pra menos': int((df['erro_pct'] < 0).sum()),
        }
        colors = ['#00cc96', '#60a5fa', '#a78bfa']
        labels = list(counts.keys())
        values = list(counts.values())

        # Pizza sólida com fatias separadas (pull) — look 3D minimalista.
        # Sem texto direto nas fatias: toda informação via hover + legenda.
        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0,
            pull=[0.06, 0.06, 0.06],
            marker={
                "colors": colors,
                "line": {"color": "#1e1e2f", "width": 2},
            },
            textinfo="percent",
            textfont=dict(size=12, color="#ffffff"),
            textposition="inside",
            hovertemplate="<b>%{label}</b><br>%{value} previsões — %{percent}<extra></extra>",
            direction="clockwise",
            sort=False,
        ))

        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top", y=-0.02,
                xanchor="center", x=0.5,
                font=dict(color="#9b9bb5", size=11),
                itemclick=False,
                itemdoubleclick=False,
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="#2c2c3e",
            margin=dict(l=10, r=10, t=10, b=55),
        )
        return fig

    @app.callback(
        Output("cards-top10-recs", "children"),
        Input("metric-picker", "value")
    )
    def render_top_recommendations(metrico):
        conn = get_connection()
        if metrico == "graham":
            query = """
                SELECT acao, lpa, vpa, cotacao, pl, roe
                FROM indicadores_fundamentalistas
                WHERE data_coleta = (
                    SELECT MAX(data_coleta) FROM indicadores_fundamentalistas
                )
                  AND lpa > 0 AND vpa > 0 AND cotacao > 0
                  AND pl >= 0 AND roe >= 0
            """
            df = pd.read_sql(query, conn)
            df[["lpa", "vpa", "cotacao"]] = df[["lpa", "vpa", "cotacao"]].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=["lpa", "vpa", "cotacao"])
            df["valor_graham"] = np.sqrt(22.5 * df["lpa"] * df["vpa"])
            df["metrica"] = df["valor_graham"] - df["cotacao"]
            top_df = df[df["metrica"] > 0].sort_values("metrica", ascending=False).head(10)
        else:
            base_query = f"""
                SELECT acao, {metrico} AS metrica
                FROM indicadores_fundamentalistas
                WHERE data_coleta = (
                    SELECT MAX(data_coleta) FROM indicadores_fundamentalistas
                ) AND {metrico} IS NOT NULL
            """
            if metrico == "dividend_yield":
                base_query = base_query.replace("WHERE", "WHERE pl >= 0 AND roe >= 0 AND")
            if metrico == "roe":
                base_query = base_query.replace("WHERE", "WHERE pl >= 0 AND lpa > 0 AND")
            df = pd.read_sql(base_query, conn)
            df["metrica"] = pd.to_numeric(df["metrica"], errors="coerce")
            df = df.dropna(subset=["metrica"])
            if metrico == "div_liq_patrimonio":
                tmp = df.sort_values("metrica").head(10)
                top_df = tmp.sort_values("metrica", ascending=False)
            else:
                top_df = df.sort_values("metrica", ascending=False).head(10)
        conn.close()

        top_actions = top_df["acao"].tolist()
        if not top_actions:
            return html.P("Sem dados para o ranking atual", className="text-muted")

        conn2 = get_connection()
        placeholders = ", ".join(["%s"] * len(top_actions))
        sql_recos = f"""
            SELECT acao, recomendada, nao_recomendada, resultado
            FROM (
                SELECT
                  acao,
                  recomendada,
                  nao_recomendada,
                  resultado,
                  ROW_NUMBER() OVER (
                    PARTITION BY acao
                    ORDER BY data_insercao DESC
                  ) AS rn
                FROM recomendacoes_acoes
                WHERE acao IN ({placeholders})
            ) sub
            WHERE rn = 1
              AND recomendada < 1
        """
        recos_df = pd.read_sql(sql_recos, conn2, params=top_actions)
        conn2.close()

        recos_df["acao"] = pd.Categorical(recos_df["acao"], categories=top_actions, ordered=True)
        recos_df = recos_df.sort_values("acao")

        cards = []
        for _, row in recos_df.iterrows():
            is_rec = "NÃO" not in row["resultado"]
            resultado_class = "recomendacao-positiva" if is_rec else "recomendacao-negativa"
            cards.append(
                dbc.Card(
                    [
                        dbc.CardHeader(row["acao"], className="text-center fw-bold"),
                        dbc.CardBody([
                            html.P(f"Recomendada: {row['recomendada'] * 100:.1f}%", className="card-text mb-1 small"),
                            html.P(f"Não Recomendada: {row['nao_recomendada'] * 100:.1f}%", className="card-text mb-2 small"),
                            html.P(
                                row["resultado"],
                                className=f"card-text fst-italic fw-bold {resultado_class}",
                                style={"whiteSpace": "pre-wrap"}
                            )
                        ])
                    ],
                    className="mb-2",
                )
            )

        return html.Div([
            html.H6(
                "Recomendação do Modelo",
                style={"color": "#9b9bb5", "textAlign": "center", "marginBottom": "0.75rem",
                       "textTransform": "uppercase", "fontSize": "0.75rem", "letterSpacing": "0.06em"}
            ),
            *cards
        ])

    @app.callback(
        Output("card-mae",  "children"),
        Output("card-mse",  "children"),
        Output("card-rmse", "children"),
        Output("card-r2",   "children"),
        Output("card-mape", "children"),
        Input("filter-data-previsao", "value"),
        Input("filter-data-calculo",  "value"),
        Input("filter-acao-ind",      "value"),
        Input("filter-erro-pct",      "value")
    )
    def update_performance_cards(data_prev, data_calc, acao_sel, erro_sel):
        df = _get_comparison_df()

        if data_prev:
            df = df[df["data_previsao"] == data_prev]
        if data_calc:
            df = df[df["data_calculo"] == data_calc]
        if acao_sel:
            df = df[df["acao"] == acao_sel]
        if erro_sel:
            masks = []
            if "gt0" in erro_sel: masks.append(df["erro_pct"] > 0)
            if "lt0" in erro_sel: masks.append(df["erro_pct"] < 0)
            if "eq0" in erro_sel: masks.append(df["erro_pct"] == 0)
            df = df[np.logical_or.reduce(masks)]

        if df.empty:
            return "–", "–", "–", "–", "–"

        errors = df["preco_previsto"] - df["preco_real"]
        mae  = errors.abs().mean()
        mse  = (errors ** 2).mean()
        rmse = np.sqrt(mse)
        mape = (errors.abs() / df["preco_real"]).mean() * 100

        y_true = df["preco_real"]
        y_pred = df["preco_previsto"]
        ss_res = ((y_true - y_pred) ** 2).sum()
        ss_tot = ((y_true - y_true.mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        return (
            f"{mae:.4f}",
            f"{mse:.4f}",
            f"{rmse:.4f}",
            f"{r2 * 100:.2f}%",
            f"{mape:.2f}%"
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _get_comparison_df():
    conn = get_connection()
    df = pd.read_sql(
        '''
        SELECT r.acao, r.data_calculo, r.data_previsao, r.preco_previsto,
               i.cotacao AS preco_real,
               CASE WHEN i.cotacao IS NOT NULL AND i.cotacao<>0
                    THEN ROUND((r.preco_previsto - i.cotacao)/i.cotacao*100,4)
                    ELSE NULL END AS erro_pct
        FROM resultados_precos r
        LEFT JOIN indicadores_fundamentalistas i
          ON r.acao=i.acao AND r.data_previsao=i.data_coleta
        ''',
        conn,
        parse_dates=['data_calculo', 'data_previsao']
    )
    conn.close()
    df['data_calculo']  = df['data_calculo'].dt.strftime('%Y-%m-%d')
    df['data_previsao'] = df['data_previsao'].dt.strftime('%Y-%m-%d')
    return df
