"""Migrações simples para bancos que já existem.

O Base.metadata.create_all() cria tabelas novas, mas não acrescenta colunas em
tabelas antigas. Aqui acrescentamos as colunas que faltam, sem apagar dados.
"""

COLUNAS_NOVAS = {
    "contas_recorrentes": [
        ("total_parcelas", "INTEGER"),
        ("parcela_inicial", "INTEGER NOT NULL DEFAULT 1"),
    ],
}


def aplicar_migracoes(engine) -> list:
    """Acrescenta as colunas ausentes. Seguro para rodar a cada início (idempotente)."""
    aplicadas = []
    conexao = engine.raw_connection()
    try:
        cursor = conexao.cursor()
        for tabela, colunas in COLUNAS_NOVAS.items():
            cursor.execute(f"PRAGMA table_info({tabela})")
            existentes = {linha[1] for linha in cursor.fetchall()}
            if not existentes:  # tabela ainda não existe: o create_all cuida dela
                continue
            for nome, definicao in colunas:
                if nome not in existentes:
                    cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")
                    aplicadas.append(f"{tabela}.{nome}")
        conexao.commit()
    finally:
        conexao.close()
    return aplicadas
