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