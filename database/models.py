from datetime import date
from database.connection import Base
from sqlalchemy import (
    Column,
    Date,
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


class Transacao(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(255), nullable=False)
    valor = Column(Float, nullable=False)

    # Validação do tipo direto no banco (Entrada ou Saída)
    tipo = Column(
        Enum("Entrada", "Saída", name="tipo_transacao_enum"),
        nullable=False,
    )

    forma_pagamento = Column(String(50), nullable=True)

    # Atribui a data atual no Python (default) e no próprio Banco (server_default)
    data = Column(
        Date,
        default=date.today,
        server_default=func.current_date(),
        nullable=False,
    )

    # FK apontando com exclusão em cascata nativa do banco
    perfil_id = Column(
        Integer,
        ForeignKey("perfis.id", ondelete="CASCADE"),
        nullable=False,
    )

    perfil = relationship("Perfil", back_populates="transacoes")