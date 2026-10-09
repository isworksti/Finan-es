from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy import extract
from database.models import CartaoCredito, Perfil, Transacao, HistoricoLimite  # Importe HistoricoLimite se existir no models.py
from utils.db import obter_sessao

MESES = [
    (str(i), m) for i, m in enumerate([
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ], start=1)
]

MAPA_MESES = {m[1]: int(m[0]) for m in MESES}

# --- AUXILIARES ---

def eh_credito(forma_pagto):
    if not forma_pagto:
        return False
    return str(forma_pagto).strip().lower() in ["crédito", "credito"]


# --- PERFIS ---

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


# --- CARTÕES DE CRÉDITO ---

def buscar_cartoes_do_perfil(perfil_id: int):
    """Retorna todos os cartões cadastrados para o perfil informado."""
    with obter_sessao() as db:
        return db.query(CartaoCredito).filter(CartaoCredito.perfil_id == perfil_id).all()


def criar_novo_cartao(nome: str, limite: float, perfil_id: int, dia_fechamento: int = None, dia_vencimento: int = None):
    """Cadastra um novo cartão de crédito associado a um perfil usando SQLAlchemy."""
    with obter_sessao() as db:
        cartao_existente = db.query(CartaoCredito).filter(
            CartaoCredito.perfil_id == perfil_id,
            CartaoCredito.nome == nome
        ).first()
        
        if cartao_existente:
            return False, "Já existe um cartão com esse nome para este perfil!"

        novo_cartao = CartaoCredito(
            nome=nome,
            limite=limite,
            perfil_id=perfil_id,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento
        )
        db.add(novo_cartao)
        db.commit()
        return True, f"Cartão '{nome}' criado com sucesso!"


def salvar_cartao(nome, limite, dia_fechamento, dia_vencimento, perfil_id):
    """Alias mantido para compatibilidade com a View, corrigido para SQLAlchemy."""
    sucesso, msg = criar_novo_cartao(
        nome=nome,
        limite=limite,
        perfil_id=perfil_id,
        dia_fechamento=dia_fechamento,
        dia_vencimento=dia_vencimento
    )
    if not sucesso:
        raise ValueError(msg)


def atualizar_cartao(cartao_id: int, nome: str, limite: float, dia_fechamento: int, dia_vencimento: int, anotacao_limite: str = None):
    """
    Atualiza os dados do cartão e grava o histórico se houver alteração de limite.
    """
    with obter_sessao() as db:
        cartao = db.query(CartaoCredito).filter(CartaoCredito.id == cartao_id).first()
        if not cartao:
            return False

        limite_anterior = cartao.limite
        cartao.nome = nome
        cartao.dia_fechamento = dia_fechamento
        cartao.dia_vencimento = dia_vencimento

        # Registrar no histórico apenas se o valor do limite realmente mudou
        if abs(limite_anterior - limite) > 0.01:
            cartao.limite = limite
            
            # Tenta gravar na tabela de histórico (se o modelo HistoricoLimite existir)
            try:
                historico = HistoricoLimite(
                    cartao_id=cartao_id,
                    limite_anterior=limite_anterior,
                    limite_novo=limite,
                    anotacao=anotacao_limite or "Alteração de limite",
                    data_alteracao=datetime.now()
                )
                db.add(historico)
            except Exception:
                pass  # Se ainda não criou a tabela HistoricoLimite no banco, não quebra a execução

        db.commit()
        return True


def buscar_historico_limite(cartao_id: int):
    """
    Retorna o histórico de alterações de limite de um cartão específico.
    """
    with obter_sessao() as db:
        try:
            return db.query(HistoricoLimite).filter(
                HistoricoLimite.cartao_id == cartao_id
            ).order_by(HistoricoLimite.data_alteracao.desc()).all()
        except Exception:
            return []


def remover_cartao(cartao_id: int):
    """Remove um cartão de crédito pelo seu ID."""
    with obter_sessao() as db:
        cartao = db.query(CartaoCredito).filter(CartaoCredito.id == cartao_id).first()
        if cartao:
            db.delete(cartao)
            db.commit()
            return True
        return False


def obter_resumo_cartoes(perfil_id: int, mes: int = None, ano: int = None):
    """
    Retorna uma lista de dicionários contendo os cartões e o total
    de gastos acumulados na fatura/período.
    """
    with obter_sessao() as db:
        cartoes = db.query(CartaoCredito).filter(CartaoCredito.perfil_id == perfil_id).all()
        resumo = []

        for c in cartoes:
            query = db.query(Transacao).filter(
                Transacao.perfil_id == perfil_id,
                Transacao.cartao_id == c.id,
                Transacao.tipo == "Saída"
            )

            if mes and ano:
                query = query.filter(
                    extract('month', Transacao.data) == mes,
                    extract('year', Transacao.data) == ano
                )

            transacoes = query.all()
            total_gasto = sum(t.valor for t in transacoes)

            resumo.append({
                "cartao": c,
                "gasto_atual": total_gasto,
                "disponivel": max(0.0, c.limite - total_gasto)
            })

        return resumo


# --- TRANSAÇÕES ---

def buscar_transacoes_do_perfil(perfil_id):
    """
    Usa o bloco 'with obter_sessao()' e joinedload para carregar
    o relacionamento com o cartão antes de fechar a sessão.
    """
    with obter_sessao() as db:
        return (
            db.query(Transacao)
            .options(joinedload(Transacao.cartao))
            .filter(Transacao.perfil_id == perfil_id)
            .all()
        )


def salvar_transacao(descricao, valor, tipo, forma_pagamento, data_dt, perfil_id, cartao_id=None):
    with obter_sessao() as db:
        if not eh_credito(forma_pagamento):
            cartao_id = None

        nova_transacao = Transacao(
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            forma_pagamento=forma_pagamento,
            data=data_dt,
            perfil_id=perfil_id,
            cartao_id=cartao_id
        )
        db.add(nova_transacao)
        db.commit()


def atualizar_transacao(transacao_id, descricao, valor, tipo, forma_pagamento, data_dt, cartao_id=None):
    with obter_sessao() as session:
        transacao = session.query(Transacao).filter(Transacao.id == transacao_id).first()

        if transacao:
            transacao.descricao = descricao
            transacao.valor = valor
            transacao.tipo = tipo
            transacao.forma_pagamento = forma_pagamento
            transacao.data = data_dt
            transacao.cartao_id = cartao_id if eh_credito(forma_pagamento) else None

            session.commit()
            return True

        return False


def remover_transacao(transacao_id: int):
    with obter_sessao() as db:
        item = db.query(Transacao).filter(Transacao.id == transacao_id).first()
        if item:
            db.delete(item)
            db.commit()
            return True
        return False