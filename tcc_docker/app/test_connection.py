from db import get_connection

try:
    conn = get_connection()
    print("✅ Conectado ao banco com sucesso!")
    conn.close()
except Exception as e:
    print("❌ Erro ao conectar:", e)
