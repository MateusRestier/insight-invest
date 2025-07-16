import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
import pandas as pd
from recomendador_acoes import recomendar_acao  # Importando a função recomendador

# Criando o app Dash com o tema Bootstrap
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout do site
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Sistema de Análise e Recomendação de Ações", className="text-center mb-4"), width=12)
    ]),
    
    # Seção de introdução sobre o projeto
    dbc.Row([
        dbc.Col(
            html.Div([
                html.H3("Sobre o Projeto", className="text-center mb-3"),
                html.P(
                    "Este sistema automatizado foi desenvolvido como parte do TCC e tem como objetivo fornecer uma análise aprofundada do desempenho de ações no mercado financeiro, "
                    "utilizando técnicas de aprendizado de máquina. O sistema coleta dados fundamentais de ações, calcula indicadores financeiros e utiliza modelos para prever o desempenho futuro das ações.",
                    className="lead text-center mb-3"
                ),
                html.P(
                    "O usuário pode visualizar gráficos interativos com as comparações entre os preços previstos e reais, além de utilizar um recomendador de ações baseado no modelo treinado para sugerir as melhores ações para compra.",
                    className="text-center mb-3"
                ),
                dbc.Button("Explorar Análises", color="primary", size="lg", href="#analises", className="d-block mx-auto")
            ]),
            width=12
        )
    ], className="mb-5"),
    
    # Seção de escolha de ação
    dbc.Row([
        dbc.Col(html.Div([
            html.H3("Escolha a Ação", className="text-center mb-3"),
            dcc.Input(id="input-ticker", type="text", value="PETR4", debounce=True, placeholder="Digite o ticker da ação (ex: PETR4)", className="mb-3", style={"width": "50%"}),
            dbc.Button("Gerar Recomendação", id="recommender-button", color="primary", size="lg", style={'width': '100%'}),
            html.Div(id="recommendation-output", className="text-center mt-4")  # Exibe a recomendação
        ]), width=12)
    ], className="mb-5"),

    # Ver mais link (expansão de recomendação)
    dbc.Row([
        dbc.Col(html.Div([
            html.Button("Ver Mais", id="show-more-button", n_clicks=0, className="btn btn-link")
        ]), width=12)
    ], id="ver-more-row", className="text-center mb-5"),

    # Seção de recomendação expandida
    dbc.Row([
        dbc.Col(html.Div(id="expanded-recommendation", style={'display': 'none'}), width=12)
    ])
])

# Função para gerar o resumo e a recomendação completa
def generate_recommendation_summary(predicao_modelo):
    summary = f"O modelo classificou como: \"{predicao_modelo}\". Probabilidades - Não Recomendada: 62.67%, Recomendada: 37.33%"
    return summary

def generate_recommendation_details(predicao_modelo):
    # Aqui, você deve substituir isso com o conteúdo completo que está sendo impresso no terminal
    # Exemplo de recomendação completa
    return f"""
        O modelo classificou a ação como: "{predicao_modelo}".
        Observações com base em regras:
        - P/L: Recomendação razoável.
        - ROE: Boa rentabilidade.
        - Ação com potencial para crescimento, etc...
    """

# Callback para gerar recomendação e mostrar detalhes
@app.callback(
    [dash.dependencies.Output('recommendation-output', 'children'),
     dash.dependencies.Output('expanded-recommendation', 'children'),
     dash.dependencies.Output('expanded-recommendation', 'style')],
    [dash.dependencies.Input('recommender-button', 'n_clicks'),
     dash.dependencies.Input('input-ticker', 'value'),
     dash.dependencies.Input('show-more-button', 'n_clicks')]
)
def update_recommendation_and_details(n_clicks, ticker, n_clicks_show_more):
    if n_clicks is None:
        return "", "", {'display': 'none'}

    # Chama a função do recomendador de ações
    result = recomendar_acao(ticker)  # Passa o ticker escolhido para o recomendador
    summary = generate_recommendation_summary(result)
    
    # Verifica se o botão "Ver Mais" foi clicado
    if n_clicks_show_more > 0:
        details = generate_recommendation_details(result)
        return summary, details, {'display': 'block'}  # Exibe os detalhes completos
    
    return summary, "", {'display': 'none'}  # Exibe apenas o resumo

if __name__ == "__main__":
    app.run(debug=True)
