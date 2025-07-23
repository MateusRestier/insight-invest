import schedule
import time
from datetime import date
from db_connection import get_connection

# importa o main do scraper
from scraper_indicadores import main as scraper_main

# importa a função de previsão do regressor
from regressor_preco import executar_pipeline_regressor

# importa nossa função paralela de recomendação em lote
from recomendador_acoes import recomendar_varias_acoes

# importa a função de backup direto
from backup import criar_backup

def tarefa_diaria():
    print("🕑 Iniciando rotina diária")

    # 1) Executa o scraper (função main)
    print("▶️ Executando scraper_indicadores.main()")
    scraper_main()

    # 2) Executa o regressor como se fosse opção “1” (n_dias=10, data_calculo=hoje)
    n_dias = 10
    data_calculo = date.today()
    print(f"▶️ Executando pipeline de regressão para {n_dias} dias a partir de {data_calculo}")
    executar_pipeline_regressor(n_dias=n_dias, data_calculo=data_calculo)

    # 3) Executa inserção em lote das recomendações
    print("▶️ Inserindo recomendações em lote no banco...")
    conn = get_connection()
    recomendar_varias_acoes(conn)

    # 4) Executa backup do banco (equivalente à opção 1)
    print("▶️ Executando backup do banco...")
    criar_backup()

    print("✅ Rotina diária concluída\n")


# agenda para rodar todo dia às 01:00
schedule.every().day.at("01:00").do(tarefa_diaria)

print("⏱ Scheduler iniciado. Aguardando próxima execução...")
while True:
    schedule.run_pending()
    time.sleep(30)


'''if __name__ == "__main__":
    tarefa_diaria()'''