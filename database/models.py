from datetime import date, datetime
from database.connection import Base
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Boolean,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship


class Perfil(Base):
    __tablename__ = "perfis"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)

    # Relacionamento com exclusão em cascata no ORM
    transacoes = relationship(
        "Transacao",
        back_populates="perfil",
        cascade="all, delete-orphan",
    )


class CartaoCredito(Base):
    __tablename__ = "cartoes_credito"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=False)
    limite = Column(Float, nullable=False, default=0.0)
    dia_fechamento = Column(Integer, nullable=True)
    dia_vencimento = Column(Integer, nullable=True)
    perfil_id = Column(Integer, ForeignKey("perfis.id"), nullable=False)

    # Relacionamento com o histórico de limites
    historico_limites = relationship(
        "HistoricoLimite",
        back_populates="cartao",
        cascade="all, delete-orphan",
    )


class HistoricoLimite(Base):
    __tablename__ = "historicos_limite"

    id = Column(Integer, primary_key=True, index=True)
    cartao_id = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=False)
    limite_anterior = Column(Float, nullable=False)
    limite_novo = Column(Float, nullable=False)
    anotacao = Column(String, nullable=True)
    data_alteracao = Column(DateTime, default=datetime.now, nullable=False)

    cartao = relationship("CartaoCredito", back_populates="historico_limites")


class Transacao(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(255), nullable=False)
    valor = Column(Float, nullable=False)
    cartao_id = Column(Integer, ForeignKey("cartoes_credito.id"), nullable=True)
    pago = Column(Boolean, default=True, nullable=False)
    cartao = relationship("CartaoCredito", backref="transacoes")

    tipo = Column(
        Enum("Entrada", "Saída", name="tipo_transacao_enum"),
        nullable=False,
    )

    forma_pagamento = Column(String(50), nullable=True)

    data = Column(
        Date,
        default=date.today,
        server_default=func.current_date(),
        nullable=False,
    )

    perfil_id = Column(
        Integer,
        ForeignKey("perfis.id", ondelete="CASCADE"),
        nullable=False,
    )

    perfil = relationship("Perfil", back_populates="transacoes")

class FaturaMensal(Base):
    """Controle de status da fatura de um cartão em um mês/ano.

    Usa o mesmo Base dos outros modelos para que Base.metadata.create_all()
    crie a tabela automaticamente.
    """

    __tablename__ = "faturas_mensais"
    __table_args__ = (
        UniqueConstraint("cartao_id", "mes", "ano", name="uq_fatura_cartao_mes_ano"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cartao_id = Column(
        Integer,
        ForeignKey("cartoes_credito.id", ondelete="CASCADE"),
        nullable=False,
    )
    mes = Column(Integer, nullable=False)
    ano = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="Aberta")  # "Aberta", "Fechada", "Paga"
    valor_pago = Column(Float, nullable=False, default=0.0)


class ContaRecorrente(Base):
    """Conta fixa que se repete todo mês (aluguel, internet, assinaturas...)."""

    __tablename__ = "contas_recorrentes"

    id = Column(Integer, primary_key=True, index=True)
    perfil_id = Column(
        Integer,
        ForeignKey("perfis.id", ondelete="CASCADE"),
        nullable=False,
    )
    descricao = Column(String(255), nullable=False)
    valor = Column(Float, nullable=False)
    dia_vencimento = Column(Integer, nullable=False)
    forma_pagamento = Column(String(50), nullable=False, default="PIX")
    # Data de inserção / início (âncora temporal para projeções e parcelamentos)
    data_inicio = Column(Date, nullable=False, default=date.today)
    # Parcelamento: prazo máximo em meses (vazio = conta sem fim, como aluguel) e
    # número da parcela no mês de data_inicio (as seguintes são calculadas)
    total_parcelas = Column(Integer, nullable=True)
    parcela_inicial = Column(Integer, nullable=False, default=1, server_default="1")

    pagamentos = relationship(
        "PagamentoConta",
        back_populates="conta",
        cascade="all, delete-orphan",
    )


class PagamentoConta(Base):
    """Registra que uma conta recorrente foi paga em um mês/ano.

    Está ligado à Transacao (saída) criada no momento do pagamento: se essa
    transação for apagada, o ON DELETE CASCADE remove este registro e a conta
    volta a aparecer como "a pagar".
    """

    __tablename__ = "pagamentos_conta"
    __table_args__ = (
        UniqueConstraint("conta_id", "mes", "ano", name="uq_pagamento_conta_mes_ano"),
    )

    id = Column(Integer, primary_key=True, index=True)
    conta_id = Column(
        Integer,
        ForeignKey("contas_recorrentes.id", ondelete="CASCADE"),
        nullable=False,
    )
    mes = Column(Integer, nullable=False)
    ano = Column(Integer, nullable=False)
    transacao_id = Column(
        Integer,
        ForeignKey("transacoes.id", ondelete="CASCADE"),
        nullable=False,
    )

    conta = relationship("ContaRecorrente", back_populates="pagamentos")

