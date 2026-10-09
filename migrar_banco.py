import sqlite3

NOME_BANCO = "financeiro.db"  

def adicionar_coluna_cartao_id():
    try:
        conn = sqlite3.connect(NOME_BANCO)
        cursor = conn.cursor()
        
        cursor.execute("""
            ALTER TABLE transacoes 
            ADD COLUMN cartao_id INTEGER REFERENCES cartoes_credito(id);
        """)
        
        conn.commit()
        conn.close()
        print("✅ Coluna 'cartao_id' adicionada com sucesso à tabela 'transacoes'!")
    except sqlite3.OperationalError as e:
        print(f"⚠️ Aviso ou Erro: {e}")

if __name__ == "__main__":
    adicionar_coluna_cartao_id()