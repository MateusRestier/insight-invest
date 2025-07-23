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
    return dbc.Container(
        [
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
                        style={"color": "#e0e0e0", "backgroundColor": "#1e1e2f", "borderColor": "#444"}
                    ), md=4
                )
            ]),
            dbc.Row([
                dbc.Col(dcc.Graph(id="grafico-top-metric"), md=8),
                dbc.Col(
                    html.Div(
                        id="cards-top3-recs",
                        style={
                            "maxHeight": "500px",    # altura similar ao gráfico
                            "overflowY": "auto",     # habilita scroll se necessário
                            "paddingRight": "1rem"
                        }
                    ),
                    md=4
                ),
            ]),

            # TÍTULO DA TABELA
            dbc.Row([
                dbc.Col(html.H5("📈 Comparação Preço Previsto x Real", className="mt-4 mb-2"), width=12)
            ]),

            # FILTROS TABELA (abaixo do título) — agora com filtro de erro_pct
            dbc.Row([
                dbc.Col(dcc.Dropdown(
                    id='filter-data-previsao',
                    options=[], placeholder='Data Previsão', clearable=True, searchable=True,
                    className='dropdown-dark',
                    style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}
                ), width=2),

                dbc.Col(dcc.Dropdown(
                    id='filter-data-calculo',
                    options=[], placeholder='Data Cálculo', clearable=True, searchable=True,
                    className='dropdown-dark',
                    style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}
                ), width=2),

                dbc.Col(dcc.Dropdown(
                    id='filter-acao-ind',
                    options=[], placeholder='Selecione Ação', clearable=True, searchable=True,
                    className='dropdown-dark',
                    style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}
                ), width=2),

                dbc.Col(dcc.Dropdown(
                    id='filter-erro-pct',
                    options=[
                        {"label":"Maior que 0", "value":"gt0"},
                        {"label":"Menor que 0", "value":"lt0"},
                        {"label":"Igual a 0",   "value":"eq0"}
                    ],
                    placeholder='Erro %', multi=True,
                    className='dropdown-dark',
                    style={"backgroundColor":"#1e1e2f","color":"#e0e0e0","borderColor":"#444"}
                ), width=2)
            ], className='mb-4'),


            # TABELA E PIE CHART alinhados no topo
            dbc.Row([
                dbc.Col(
                    dash_table.DataTable(
                        id="table-previsto-real", page_size=10,
                        style_table={"overflowX": "auto"},
                        style_header={"backgroundColor": "#5561ff", "color": "#ffffff", "fontWeight": "bold"},
                        style_cell={"backgroundColor": "#1e1e2f", "color": "#e0e0e0", "textAlign": "center", "padding": "5px"},
                        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "#5561ff", "color": "#ffffff"}]
                    ), width=8
                ),
                dbc.Col(
                    dcc.Graph(
                        id='pie-error-dist',
                        config={'displayModeBar': False},
                        style={'marginTop': '-50px'}  # eleva um pouco o pie-chart
                    ), width=4)
            ], className='mb-5 align-items-start')
        ],
        fluid=True,
        style={"padding": "0 1rem"}
    )

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
                labels={'acao':'Ação', 'metrica': y_label},
                category_orders={'acao': df['acao'].tolist()}
            )
            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig.update_layout(
                margin=dict(l=24, r=24, t=40, b=24),
                plot_bgcolor='#1e1e2f', paper_bgcolor='#1e1e2f',
                font=dict(color='#e0e0e0')
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
        cols = [{'name': col.replace('_',' ').title(), 'id': col} for col in df.columns]
        return data, cols

    @app.callback(
        Output('pie-error-dist', 'figure'),
        Input('filter-data-previsao', 'value'),
        Input('filter-data-calculo', 'value'),
        Input('filter-acao-ind', 'value'),
        Input('filter-erro-pct', 'value')
    )
    def plot_error_distribution(data_prev, data_calc, acao_sel, erro_sel):
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

        counts = {
            'Igual a 0': (df['erro_pct'] == 0).sum(),
            'Maior que 0': (df['erro_pct'] > 0).sum(),
            'Menor que 0': (df['erro_pct'] < 0).sum()
        }
        means = {
            'Igual a 0': df.loc[df['erro_pct'] == 0, 'erro_pct'].mean() or 0,
            'Maior que 0': df.loc[df['erro_pct'] > 0, 'erro_pct'].mean() or 0,
            'Menor que 0': df.loc[df['erro_pct'] < 0, 'erro_pct'].mean() or 0
        }

        pie_df = pd.DataFrame({
            'Status': list(counts.keys()),
            'Count': list(counts.values()),
            'Mean':  [means[k] for k in counts.keys()]
        })

        fig = px.pie(
            pie_df,
            names='Status',
            values='Count',
            title='Distribuição Erro Pct',
            custom_data=['Mean']
        )
        fig.update_traces(
            textinfo='label+percent',
            hovertemplate='%{label}: %{percent}<br>Média erro: %{customdata[0]:.2f}'
        )
        fig.update_layout(
            plot_bgcolor='#1e1e2f',
            paper_bgcolor='#1e1e2f',
            font=dict(color='#e0e0e0'),
            margin=dict(l=20, r=20, t=50, b=20)
        )
        return fig

    @app.callback(
        Output("cards-top3-recs", "children"),
        Input("metric-picker", "value")
    )
    def render_top_recommendations(_):
        conn = get_connection()
        sql = """
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
        ) sub
        WHERE rn = 1
          AND recomendada < 1
        ORDER BY recomendada DESC
        LIMIT 10
        """
        df = pd.read_sql(sql, conn)
        conn.close()

        cards = []
        for _, row in df.iterrows():
            cards.append(
                dbc.Card(
                    [
                        dbc.CardHeader(row["acao"], className="text-center"),
                        dbc.CardBody(
                            [
                                html.P(f"Recomendada: {row['recomendada']:.4f}", className="card-text"),
                                html.P(f"Não Recomendada: {row['nao_recomendada']:.4f}", className="card-text"),
                                html.P(
                                    row["resultado"],
                                    className="card-text fst-italic",
                                    style={"whiteSpace": "pre-wrap"}
                                )
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

        if not cards:
            return html.P("Sem recomendações disponíveis", className="text-muted")

        return html.Div(
            [
                html.H5(
                    "Top 10 ações recomendadas",
                    style={
                        "color": "#e0e0e0",
                        "textAlign": "center",
                        "marginBottom": "1rem"
                    }
                ),
                *cards
            ],
            style={
                "maxHeight": "450px",
                "overflowY": "scroll",
                "padding": "0 0.5rem"
            }
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
