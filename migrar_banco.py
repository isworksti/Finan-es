import sqlite3

# Altere para o nome do seu arquivo .db (ex: "financeiro.db" ou "banco.db")
NOME_BANCO = "financeiro.db"  

conn = sqlite3.connect(NOME_BANCO)
cursor = conn.cursor()

try:
    # Adiciona a coluna 'data' do tipo DATE com valor padrão sendo a data atual (YYYY-MM-DD)
    cursor.execute("ALTER TABLE transacoes ADD COLUMN data DATE DEFAULT (DATE('now'));")
    conn.commit()
    print("Coluna 'data' adicionada com sucesso!")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("A coluna 'data' já existe.")
    else:
        print(f"Erro ao atualizar banco: {e}")
finally:
    conn.close()