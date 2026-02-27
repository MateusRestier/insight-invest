
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import numpy as np
from dash import dash_table

from db_connection import get_connection

# ----------------------------------------------------------------------
# Layout da página "Indicadores"
# ----------------------------------------------------------------------
def layout_indicadores():
    # Cards de performance para facilitar grid responsivo
    performance_cards = [
        dbc.Card(
            dbc.CardBody([
                html.Span("MAE", className="fw-bold"),
                html.Span(id="card-mae")
            ], className="d-flex justify-content-between align-items-center", style={"padding":"0 1rem"}),
            id="card-mae-container",
            style={"backgroundColor":"#2c2c3e","color":"#e0e0e0","height":"40px"}
        ),
        dbc.Card(
            dbc.CardBody([
                html.Span("MSE", className="fw-bold"),
                html.Span(id="card-mse")
            ], className="d-flex justify-content-between align-items-center", style={"padding":"0 1rem"}),
            id="card-mse-container",
            style={"backgroundColor":"#2c2c3e","color":"#e0e0e0","height":"40px"}
        ),
        dbc.Card(
            dbc.CardBody([
                html.Span("RMSE", className="fw-bold"),
                html.Span(id="card-rmse")
            ], className="d-flex justify-content-between align-items-center", style={"padding":"0 1rem"}),
            id="card-rmse-container",
            style={"backgroundColor":"#2c2c3e","color":"#e0e0e0","height":"40px"}
        ),
        dbc.Card(
            dbc.CardBody([
                html.Span("R²", className="fw-bold"),
                html.Span(id="card-r2")
            ], className="d-flex justify-content-between align-items-center", style={"padding":"0 1rem"}),
            id="card-r2-container",
            style={"backgroundColor":"#2c2c3e","color":"#e0e0e0","height":"40px"}
        ),
        dbc.Card(
            dbc.CardBody([
                html.Span("MAPE", className="fw-bold"),
                html.Span(id="card-mape")
            ], className="d-flex justify-content-between align-items-center", style={"padding":"0 1rem"}),
            id="card-mape-container",
            style={"backgroundColor":"#2c2c3e","color":"#e0e0e0","height":"40px"}
        ),
    ]

    return dbc.Container(fluid=True, children=[
        html.H3("📊 Indicadores Fundamentalistas", className="mb-4"),

        # SELECT + GRÁFICO
        dbc.Row([
            dbc.Col(
                dbc.Select(
                    id="metric-picker",
                    value="graham",
                    options=[
                        {"label": "Top 10 ações com maior desconto segundo Graham (PL e ROE positivos)", "value": "graham"},
                        {"label": "Top 10 ações com maior Dividend Yield (PL e ROE positivos)", "value": "dividend_yield"},
                        {"label": "Top 10 ações com maior ROE (PL e LPA positivos)", "value": "roe"},
                        {"label": "Top 10 ações com cotação mais alta", "value": "cotacao"},
                        {"label": "Top 10 ações com maior Margem Líquida (%)", "value": "margem_liquida"},
                        {"label": "Top 10 ações com menor Dívida Líq./Patrimônio", "value": "div_liq_patrimonio"},
                    ],
                    className="mb-3 dropdown-dark",
                    style={"color":"#e0e0e0","backgroundColor":"#1e1e2f","borderColor":"#444"}
                ),
                xs=12, sm=12, md=4
            )
        ]),

        # Top-10 e recomendações
        dbc.Row([
            dbc.Col(dcc.Graph(id="grafico-top-metric"), xs=12, md=8),
            dbc.Col(
                html.Div(
                    id="cards-top10-recs",
                    style={"maxHeight":"450px","overflowY":"scroll","padding":"0 0.5rem"}
                ), xs=12, md=4
            )
        ], className="mb-4"),

        # TÍTULO DA TABELA
        dbc.Row([
            dbc.Col(html.H5("📈 Comparação Preço Previsto x Real", className="mb-4"), width=12)
        ]),

        # FILTROS TABELA (logo abaixo do título da tabela)
        dbc.Row([
            dbc.Col(dcc.Dropdown(id='filter-data-previsao', options=[], placeholder='Data Previsão', clearable=True,
                                 searchable=True, className='dropdown-dark',
                                 style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}), xs=12, sm=6, md=3),
            dbc.Col(dcc.Dropdown(id='filter-data-calculo', options=[], placeholder='Data Cálculo', clearable=True,
                                 searchable=True, className='dropdown-dark',
                                 style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}), xs=12, sm=6, md=3),
            dbc.Col(dcc.Dropdown(id='filter-acao-ind', options=[], placeholder='Selecione Ação', clearable=True,
                                 searchable=True, className='dropdown-dark',
                                 style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}), xs=12, sm=6, md=3),
            dbc.Col(dcc.Dropdown(id='filter-erro-pct',
                                 options=[{'label':'Maior que 0','value':'gt0'},{'label':'Menor que 0','value':'lt0'},{'label':'Igual a 0','value':'eq0'}],
                                 placeholder='Erro %', multi=True, className='dropdown-dark',
                                 style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}), xs=12, sm=6, md=3)
        ], className='g-2 filtros-indicadores mb-4'),

        # Performance do modelo (cards responsivos, ocupando toda a largura)
        dbc.Row(
            html.Div(
                performance_cards,
                className="performance-cards-row g-2 mb-4",
                style={"width": "100%", "margin": "0"}
            ),
            className="mb-4"
        ),

        # Tooltips para explicação
        dbc.Tooltip("MAE (Mean Absolute Error): média dos erros absolutos entre preços previstos e reais.", target="card-mae-container", placement="top"),
        dbc.Tooltip("MSE (Mean Squared Error): média dos quadrados dos erros entre preços previstos e reais.", target="card-mse-container", placement="top"),
        dbc.Tooltip("RMSE (Root Mean Squared Error): raiz do MSE, erro médio ponderado.", target="card-rmse-container", placement="top"),
        dbc.Tooltip("R² (Coeficiente de Determinação): proporção da variância do preço real explicada.", target="card-r2-container", placement="top"),
        dbc.Tooltip("MAPE (Mean Absolute Percentage Error): erro percentual médio.", target="card-mape-container", placement="top"),

        # Tabela e gráfico de pizza responsivos
        dbc.Row([
            dbc.Col(
                html.Div(
                    dash_table.DataTable(
                        id="table-previsto-real", page_size=10,
                        style_table={"minWidth": "100%"},
                        style_header={"backgroundColor":"#5561ff","color":"#ffffff","fontWeight":"bold"},
                        style_cell={"backgroundColor":"#1e1e2f","color":"#e0e0e0","textAlign":"center","padding":"5px","whiteSpace":"normal","height":"auto"},
                        style_data_conditional=[{"if":{"state":"selected"},"backgroundColor":"#5561ff","color":"#ffffff"}],
                        sort_action='native'
                    ),
                    className="table-responsive"
                ),
                xs=12, lg=8
            ),
            dbc.Col(
                dcc.Graph(
                    id='pie-error-dist',
                    config={'displayModeBar': False},
                    style={'marginTop':'10px'},
                    clear_on_unhover=True
                ),
                xs=12, lg=4
            )
        ], className='mb-5 align-items-start')
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
                df[["lpa","vpa","cotacao"]] = df[["lpa","vpa","cotacao"]].apply(pd.to_numeric, errors='coerce')
                df = df.dropna(subset=['lpa','vpa','cotacao'])
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
                labels={'acao':'', 'metrica': y_label},
                category_orders={'acao': df['acao'].tolist()}
            )
            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                plot_bgcolor='#1e1e2f', paper_bgcolor='#1e1e2f',
                font=dict(color='#e0e0e0'),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.2)'  # linhas horizontais com transparência
                )
            )
            return fig

        except Exception as e:
            return px.bar(title=f"Erro ao gerar gráfico: {e}")

    @app.callback(
        Output('filter-data-previsao', 'options'),
        Input('metric-picker', 'value')
    )
    def populate_previsao_options(_):
        df = _get_comparison_df()
        dates = df['data_previsao'].dt.strftime('%Y-%m-%d').unique()
        return [{'label': d, 'value': d} for d in sorted(dates)]

    @app.callback(
        Output('filter-data-calculo', 'options'),
        Input('metric-picker', 'value')
    )
    def populate_calculo_options(_):
        df = _get_comparison_df()
        dates = df['data_calculo'].dt.strftime('%Y-%m-%d').unique()
        return [{'label': d, 'value': d} for d in sorted(dates)]

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
        df['data_previsao'] = df['data_previsao'].dt.strftime('%Y-%m-%d')
        df['data_calculo'] = df['data_calculo'].dt.strftime('%Y-%m-%d')

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

        data = df.to_dict('records')
        cols = [
            {"name": "Ação",           "id": "acao"},
            {"name": "Data Cálculo",   "id": "data_calculo"},
            {"name": "Data Previsão",  "id": "data_previsao"},
            {"name": "Preço Previsto", "id": "preco_previsto"},
            {"name": "Preço Real",     "id": "preco_real"},
            {"name": "Erro (%)",       "id": "erro_pct"},
        ]
        return data, cols


    @app.callback(
        Output('pie-error-dist', 'figure'),
        Input('filter-data-previsao', 'value'),
        Input('filter-data-calculo', 'value'),
        Input('filter-acao-ind', 'value'),
        Input('filter-erro-pct', 'value'),
        Input('pie-error-dist', 'hoverData')
    )
    def plot_error_distribution(data_prev, data_calc, acao_sel, erro_sel, hover_data):
        df = _get_comparison_df()
        # df['data_previsao'] = df['data_previsao'].dt.strftime('%Y-%m-%d') # Removido para evitar erro se já for string
        df['data_calculo'] = df['data_calculo'].dt.strftime('%Y-%m-%d')

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
            'Igual a 0': (df['erro_pct'] == 0).sum(),
            'Maior que 0': (df['erro_pct'] > 0).sum(),
            'Menor que 0': (df['erro_pct'] < 0).sum()
        }

        pie_df = pd.DataFrame({
            'Status': list(counts.keys()),
            'Count': list(counts.values())
        })

        # Mapeamento de cores para garantir consistência visual
        color_map = {
            'Igual a 0': 'rgb(0, 204, 150)',      # Verde
            'Maior que 0': 'rgb(126, 135, 255)',  # Roxo claro
            'Menor que 0': 'rgb(85, 61, 186)'     # Roxo escuro
        }

        fig = px.pie(
            pie_df,
            names='Status',
            values='Count',
            color='Status',
            color_discrete_map=color_map
        )

        # Lógica para destacar a fatia com hover
        pull_values = [0] * len(pie_df)
        ordered_colors = pie_df['Status'].map(color_map).tolist()
        final_colors = list(ordered_colors)

        # Configuração da "iluminação" (borda que simula um brilho)
        line_colors = ['#1e1e2f'] * len(final_colors) # Cor de fundo para borda padrão
        line_widths = [1] * len(final_colors)

        if hover_data and hover_data['points']:
            point_index = hover_data['points'][0]['pointNumber']
            pull_values[point_index] = 0.05 # "Puxa" a fatia sutilmente

            # Efeito de iluminação na fatia com hover
            line_colors[point_index] = 'rgba(126,135,255,0.8)' #
            line_widths[point_index] = 3 # Largura do brilho

            # Efeito de foco: torna as outras fatias mais transparentes
            for i in range(len(final_colors)):
                if i != point_index:
                    final_colors[i] = final_colors[i].replace('rgb', 'rgba').replace(')', ', 0.8)')
        fig.update_traces(
            pull=pull_values,
            marker={'colors': final_colors, 'line': {'color': line_colors, 'width': line_widths}},
            textinfo='label+percent',
            hovertemplate='%{label}: %{percent}'
        )
        fig.update_layout(
            title='Distribuição Erro Percentual',
            title_font=dict(size=20), 
            plot_bgcolor='#1e1e2f',
            paper_bgcolor='#1e1e2f',
            font=dict(color='#e0e0e0'),
            margin=dict(l=20, r=20, t=50, b=20),
            transition_duration=500 # Animação mais lenta e suave
        )
        return fig

    @app.callback(
        Output("cards-top10-recs", "children"),
        Input("metric-picker", "value")
    )
    def render_top_recommendations(metrico):
        # 1) buscar as top 10 ações para o gráfico da métrica selecionada
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
            df[["lpa","vpa","cotacao"]] = df[["lpa","vpa","cotacao"]].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=["lpa","vpa","cotacao"])
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

        # 2) buscar as recomendações mais recentes dessas ações
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

        # 3) reordenar pelos mesmos top_actions
        recos_df["acao"] = pd.Categorical(recos_df["acao"], categories=top_actions, ordered=True)
        recos_df = recos_df.sort_values("acao")

        # 4) montar os cards
        cards = []
        for _, row in recos_df.iterrows():
            cards.append(
                dbc.Card(
                    [
                        dbc.CardHeader(row["acao"], className="text-center"),
                        dbc.CardBody(
                            [
                                html.P(f"Recomendada: {row['recomendada'] * 100:.2f}%", className="card-text"),
                                html.P(f"Não Recomendada: {row['nao_recomendada'] * 100:.2f}%", className="card-text"),
                                html.P(row["resultado"], 
                                    className="card-text fst-italic " + (
                                        "recomendacao-negativa" if "NÃO" in row["resultado"] else "recomendacao-positiva"
                                       ),
                                       style={"whiteSpace": "pre-wrap"})
                            ]
                        )
                    ],
                    className="mb-2",
                    style={
                        "backgroundColor": "#2c2c3e",
                        "color": "#e0e0e0"
                    }
                )
            )

        # 5) retornar com título e scroll
        return html.Div(
            [
                html.H5(
                    "Classificação das Ações à Esquerda",
                    style={"color": "#e0e0e0", "textAlign": "center", "marginBottom": "1rem"}
                ),
                *cards
            ],
            style={
                "maxHeight": "450px",
                "overflowY": "scroll",
                "padding": "0 0.5rem"
            }
        )
    
    @app.callback(
        Output("card-mae",   "children"),
        Output("card-mse",   "children"),
        Output("card-rmse",  "children"),
        Output("card-r2",    "children"),
        Output("card-mape",  "children"),
        Input("filter-data-previsao", "value"),
        Input("filter-data-calculo",  "value"),
        Input("filter-acao-ind",      "value"),
        Input("filter-erro-pct",      "value")
    )
    def update_performance_cards(data_prev, data_calc, acao_sel, erro_sel):
        # busca os dados de comparação
        df = _get_comparison_df()

        # aplica filtros iguais aos da tabela
        if data_prev:
            df = df[df["data_previsao"] == data_prev]
        if data_calc:
            df = df[df["data_calculo"]  == data_calc]
        if acao_sel:
            df = df[df["acao"] == acao_sel]
        if erro_sel:
            masks = []
            if "gt0" in erro_sel: masks.append(df["erro_pct"] > 0)
            if "lt0" in erro_sel: masks.append(df["erro_pct"] < 0)
            if "eq0" in erro_sel: masks.append(df["erro_pct"] == 0)
            df = df[np.logical_or.reduce(masks)]

        # se não houver dados, exibe traço
        if df.empty:
            return "–", "–", "–", "–", "–"

        # cálculos
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

        # formatação
        return (
            f"{mae:.6f}",
            f"{mse:.6f}",
            f"{rmse:.6f}",
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
        parse_dates=['data_calculo','data_previsao']
    )
    conn.close()
    return df
