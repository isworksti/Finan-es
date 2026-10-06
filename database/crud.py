from database.models import Perfil, Transacao
from utils.db import obter_sessao

MESES = [
    ("1", "Janeiro"),
    ("2", "Fevereiro"),
    ("3", "Março"),
    ("4", "Abril"),
    ("5", "Maio"),
    ("6", "Junho"),
    ("7", "Julho"),
    ("8", "Agosto"),
    ("9", "Setembro"),
    ("10", "Outubro"),
    ("11", "Novembro"),
    ("12", "Dezembro"),
]

MAPA_MESES = {m[1]: int(m[0]) for m in MESES}

def eh_credito(forma_pagto):
    if not forma_pagto:
        return False
    return str(forma_pagto).strip().lower() in ["crédito", "credito"]

def atualizar_transacao(transacao_id, descricao, valor, tipo, forma_pagamento, data_dt):
    session = session()    
    try:
        transacao = session.query(Transacao).filter(Transacao.id == transacao_id).first()
        if transacao:
            transacao.descricao = descricao
            transacao.valor = valor
            transacao.tipo = tipo
            transacao.forma_pagamento = forma_pagamento
            
            transacao.data = data_dt 
            
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def buscar_todos_perfis():
    with obter_sessao() as db:
        return db.query(Perfil).all()

def criar_novo_perfil(nome: str):
    with obter_sessao() as db:
        if db.query(Perfil).filter(Perfil.nome == nome).first():
            return False, "Perfil já existe!"
        db.add(Perfil(nome=nome))
        db.commit()
        return True, f"Perfil '{nome}' criado com sucesso!"

def buscar_transacoes_do_perfil(perfil_id: int):
    with obter_sessao() as db:
        return db.query(Transacao).filter(Transacao.perfil_id == perfil_id).all()

def salvar_transacao(descricao, valor, tipo, forma_pagamento, data_dt, perfil_id):
    with obter_sessao() as db:
        nova_transacao = Transacao(
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            forma_pagamento=forma_pagamento,
            data=data_dt,
            perfil_id=perfil_id,
        )
        db.add(nova_transacao)
        db.commit()

def remover_transacao(transacao_id: int):
    with obter_sessao() as db:
        item = db.query(Transacao).filter(Transacao.id == transacao_id).first()
        if item:
            db.delete(item)
            db.commit()
            return True
        return False