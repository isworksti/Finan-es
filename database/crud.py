from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import extract
from sqlalchemy.orm import joinedload

from database.models import (
    CartaoCredito,
    ContaRecorrente,
    FaturaMensal,
    HistoricoLimite,
    PagamentoConta,
    Perfil,
    Transacao,
)
from utils.db import obter_sessao
from services.contas_service import (
    calcular_parcela_inicial,
    data_vencimento_no_mes,
    numero_parcela,
)
from services.fatura_service import calcular_comprometido  # fatura_service não importa nada de database/


MESES = [
    (str(i), m)
    for i, m in enumerate(
        [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ],
        start=1,
    )
]

MAPA_MESES = {m[1]: int(m[0]) for m in MESES}


# --- AUXILIARES ---


def eh_credito(forma_pagto) -> bool:
    if not forma_pagto:
        return False
    return str(forma_pagto).strip().lower() in ["crédito", "credito"]


def _dividir_centavos(valor_total: float, total_parcelas: int) -> list[float]:
    """
    Divide um valor monetário em 'total_parcelas' usando centavos inteiros.
    O resto da divisão inteira vai para a última parcela, garantindo soma exata.
    """
    num_parcelas = max(1, int(total_parcelas))
    total_centavos = round(float(valor_total) * 100)
    base_centavos = total_centavos // num_parcelas
    resto_centavos = total_centavos - base_centavos * num_parcelas

    valores = []
    for i in range(num_parcelas):
        centavos = base_centavos + (resto_centavos if i == num_parcelas - 1 else 0)
        valores.append(centavos / 100)
    return valores


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
        return (
            db.query(CartaoCredito)
            .filter(CartaoCredito.perfil_id == perfil_id)
            .all()
        )


def calcular_limites_cartao(cartao_id: int) -> dict:
    """Calcula o limite total, comprometido e disponível de um cartão específico."""
    with obter_sessao() as db:
        cartao = db.query(CartaoCredito).filter(CartaoCredito.id == cartao_id).first()
        if not cartao:
            return {"total": 0.0, "comprometido": 0.0, "disponivel": 0.0}

        limite_total = getattr(cartao, "limite", 0.0) or 0.0

        # Busca todas as transações vinculadas a este cartão
        transacoes = db.query(Transacao).filter(Transacao.cartao_id == cartao_id).all()

        faturas = (
            db.query(FaturaMensal)
            .filter(FaturaMensal.cartao_id == cartao_id)
            .all()
        )

        # Faturas marcadas como "Paga" não consomem mais o limite do cartão
        faturas_pagas = {
            (f.mes, f.ano)
            for f in faturas
            if f.status == "Paga"
        }

        # Abatimentos parciais registrados em faturas ainda não marcadas como "Paga"
        abatimentos_parciais = sum(
            float(getattr(f, "valor_pago", 0.0) or 0.0)
            for f in faturas
            if f.status != "Paga"
        )

        comprometido_bruto = calcular_comprometido(
            transacoes, cartao.dia_fechamento, faturas_pagas
        )
        comprometido = max(0.0, comprometido_bruto - abatimentos_parciais)
        disponivel = max(0.0, limite_total - comprometido)

        return {
            "total": limite_total,
            "comprometido": comprometido,
            "disponivel": disponivel,
        }


def criar_novo_cartao(
    nome: str,
    limite: float,
    perfil_id: int,
    dia_fechamento: int = None,
    dia_vencimento: int = None,
):
    """Cadastra um novo cartão de crédito associado a um perfil usando SQLAlchemy."""
    with obter_sessao() as db:
        cartao_existente = (
            db.query(CartaoCredito)
            .filter(
                CartaoCredito.perfil_id == perfil_id, CartaoCredito.nome == nome
            )
            .first()
        )

        if cartao_existente:
            return (
                False,
                "Já existe um cartão com esse nome para este perfil!",
            )

        novo_cartao = CartaoCredito(
            nome=nome,
            limite=limite,
            perfil_id=perfil_id,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento,
        )
        db.add(novo_cartao)
        db.commit()
        return True, f"Cartão '{nome}' criado com sucesso!"


def salvar_cartao(
    nome: str,
    limite: float,
    dia_fechamento: int,
    dia_vencimento: int,
    perfil_id: int,
    cartao_id: int = None,
):
    """
    Salva um cartão: Atualiza se 'cartao_id' for informado; cria um novo caso contrário.
    """
    if cartao_id:
        sucesso = atualizar_cartao(
            cartao_id=cartao_id,
            nome=nome,
            limite=limite,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento,
        )
        if not sucesso:
            raise ValueError("Não foi possível atualizar o cartão especificado.")
    else:
        sucesso, msg = criar_novo_cartao(
            nome=nome,
            limite=limite,
            perfil_id=perfil_id,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento,
        )
        if not sucesso:
            raise ValueError(msg)


def atualizar_cartao(
    cartao_id: int,
    nome: str,
    limite: float,
    dia_fechamento: int,
    dia_vencimento: int,
    anotacao_limite: str = None,
):
    """
    Atualiza os dados do cartão e grava o histórico se houver alteração de limite.
    """
    with obter_sessao() as db:
        cartao = (
            db.query(CartaoCredito)
            .filter(CartaoCredito.id == cartao_id)
            .first()
        )
        if not cartao:
            return False

        limite_anterior = cartao.limite or 0.0
        cartao.nome = nome
        cartao.dia_fechamento = dia_fechamento
        cartao.dia_vencimento = dia_vencimento

        # Registrar no histórico apenas se o valor do limite realmente mudou
        if abs(limite_anterior - limite) > 0.01:
            cartao.limite = limite

            try:
                historico = HistoricoLimite(
                    cartao_id=cartao_id,
                    limite_anterior=limite_anterior,
                    limite_novo=limite,
                    anotacao=anotacao_limite or "Alteração de limite",
                    data_alteracao=datetime.now(),
                )
                db.add(historico)
            except Exception:
                pass

        db.commit()
        return True


def buscar_historico_limite(cartao_id: int):
    """
    Retorna o histórico de alterações de limite de um cartão específico.
    """
    with obter_sessao() as db:
        try:
            return (
                db.query(HistoricoLimite)
                .filter(HistoricoLimite.cartao_id == cartao_id)
                .order_by(HistoricoLimite.data_alteracao.desc())
                .all()
            )
        except Exception:
            return []


def deletar_cartao(cartao_id: int) -> bool:
    """Remove um cartão pelo seu ID (alias para compatibilidade)."""
    return remover_cartao(cartao_id)


def remover_cartao(cartao_id: int) -> bool:
    """Remove um cartão de crédito pelo seu ID."""
    with obter_sessao() as db:
        cartao = (
            db.query(CartaoCredito)
            .filter(CartaoCredito.id == cartao_id)
            .first()
        )
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
        cartoes = (
            db.query(CartaoCredito)
            .filter(CartaoCredito.perfil_id == perfil_id)
            .all()
        )
        resumo = []

        for c in cartoes:
            query = db.query(Transacao).filter(
                Transacao.perfil_id == perfil_id,
                Transacao.cartao_id == c.id,
                Transacao.tipo == "Saída",
            )

            if mes and ano:
                query = query.filter(
                    extract("month", Transacao.data) == mes,
                    extract("year", Transacao.data) == ano,
                )

            transacoes = query.all()
            total_gasto = sum(t.valor for t in transacoes)

            resumo.append(
                {
                    "cartao": c,
                    "gasto_atual": total_gasto,
                    "disponivel": max(0.0, (c.limite or 0.0) - total_gasto),
                }
            )

        return resumo


# --- TRANSAÇÕES ---


def buscar_transacoes_do_perfil(perfil_id: int):
    """
    Busca todas as transações cadastradas para o perfil.
    """
    with obter_sessao() as db:
        return (
            db.query(Transacao)
            .options(joinedload(Transacao.cartao))
            .filter(Transacao.perfil_id == perfil_id)
            .all()
        )


def salvar_transacao(
    descricao: str,
    valor: float,
    tipo: str,
    forma_pagamento: str,
    data_dt: date,
    perfil_id: int,
    cartao_id: int = None,
    parcelas: int = 1,
):
    """
    Salva uma ou múltiplas transações (em caso de parcelamento).
    """
    with obter_sessao() as db:
        if not eh_credito(forma_pagamento):
            cartao_id = None
            parcelas = 1

        num_parcelas = max(1, int(parcelas))
        valores_parcelas = _dividir_centavos(valor, num_parcelas)

        for i, valor_parcela in enumerate(valores_parcelas):
            data_parcela = data_dt + relativedelta(months=i)
            desc_final = (
                f"{descricao} ({i+1}/{num_parcelas})"
                if num_parcelas > 1
                else descricao
            )

            nova_transacao = Transacao(
                descricao=desc_final,
                valor=valor_parcela,
                tipo=tipo,
                forma_pagamento=forma_pagamento,
                data=data_parcela,
                perfil_id=perfil_id,
                cartao_id=cartao_id,
            )
            db.add(nova_transacao)

        db.commit()


def atualizar_transacao(
    transacao_id: int,
    descricao: str,
    valor: float,
    tipo: str,
    forma_pagamento: str,
    data_dt: date,
    cartao_id: int = None,
):
    with obter_sessao() as session:
        transacao = (
            session.query(Transacao)
            .filter(Transacao.id == transacao_id)
            .first()
        )

        if transacao:
            transacao.descricao = descricao
            transacao.valor = valor
            transacao.tipo = tipo
            transacao.forma_pagamento = forma_pagamento
            transacao.data = data_dt
            transacao.cartao_id = (
                cartao_id if eh_credito(forma_pagamento) else None
            )

            session.commit()
            return True

        return False


def remover_transacao(transacao_id: int) -> bool:
    with obter_sessao() as db:
        item = (
            db.query(Transacao).filter(Transacao.id == transacao_id).first()
        )
        if item:
            db.delete(item)
            db.commit()
            return True
        return False

def _calcular_status_inicial_fatura(
    mes: int,
    ano: int,
    dia_fechamento: int | None = None,
    data_registro: date | None = None,
) -> str:
    ref = data_registro or date.today()
    if (ano, mes) < (ref.year, ref.month):
        return "Fechada"
    if (ano, mes) == (ref.year, ref.month) and dia_fechamento:
        if ref.day > int(dia_fechamento):
            return "Fechada"
    return "Aberta"

def obter_ou_criar_fatura_mensal(
    cartao_id: int,
    mes: int,
    ano: int,
    data_registro: date | None = None,
):
    """Busca o registro de controle da fatura do mês/ano ou cria com status conforme a data."""
    with obter_sessao() as db:
        fatura = (
            db.query(FaturaMensal)
            .filter(
                FaturaMensal.cartao_id == cartao_id,
                FaturaMensal.mes == mes,
                FaturaMensal.ano == ano,
            )
            .first()
        )
        if not fatura:
            cartao = db.query(CartaoCredito).filter(CartaoCredito.id == cartao_id).first()
            dia_fech = getattr(cartao, "dia_fechamento", None) if cartao else None
            data_ref = (
                data_registro
                or (getattr(cartao, "data_cadastro", None) if cartao else None)
                or (getattr(cartao, "data_registro", None) if cartao else None)
                or date.today()
            )
            if hasattr(data_ref, "date"):
                data_ref = data_ref.date()

            status_inicial = _calcular_status_inicial_fatura(mes, ano, dia_fech, data_ref)
            fatura = FaturaMensal(
                cartao_id=cartao_id,
                mes=mes,
                ano=ano,
                status=status_inicial,
                valor_pago=0.0,
            )
            db.add(fatura)
            db.commit()
            db.refresh(fatura)
        return fatura


def atualizar_status_fatura(
    cartao_id: int,
    mes: int,
    ano: int,
    novo_status: str,
    valor_pago: float | None = None,
):
    """Atualiza o status (e opcionalmente o valor_pago) de uma fatura específica."""
    with obter_sessao() as db:
        fatura = (
            db.query(FaturaMensal)
            .filter(
                FaturaMensal.cartao_id == cartao_id,
                FaturaMensal.mes == mes,
                FaturaMensal.ano == ano,
            )
            .first()
        )
        if not fatura:
            fatura = FaturaMensal(
                cartao_id=cartao_id,
                mes=mes,
                ano=ano,
                status=novo_status,
                valor_pago=float(valor_pago or 0.0),
            )
            db.add(fatura)
        else:
            fatura.status = novo_status
            if valor_pago is not None:
                fatura.valor_pago = float(valor_pago)
        db.commit()
        return True


def buscar_parcelamentos_ativos(perfil_id: int):
    """
    Retorna transações que contêm padrão de parcelas (ex: '(1/10)')
    para acompanhamento dos pagamentos a prazo.
    """
    with obter_sessao() as db:
        transacoes = (
            db.query(Transacao)
            .filter(
                Transacao.perfil_id == perfil_id,
                Transacao.descricao.like("%(%)%"),
            )
            .order_by(Transacao.data.desc())
            .all()
        )
        return transacoes


def alternar_status_pagamento(transacao_id: int, pago: bool) -> bool:
    """Atualiza o estado de pagamento (pago/não pago) de uma transação."""
    with obter_sessao() as db:
        transacao = db.query(Transacao).filter(Transacao.id == transacao_id).first()
        if transacao:
            transacao.pago = pago
            db.commit()
            return True
        return False


# --- CONTAS RECORRENTES ---


def obter_contas_do_mes(perfil_id: int, mes: int, ano: int) -> list:
    """
    Lista as contas recorrentes do perfil que valem para o mês/ano, já com o
    status de pagamento. Retorna dicionários simples (sem objetos do banco).
    """
    inicio_mes = date(ano, mes, 1)
    with obter_sessao() as db:
        contas = (
            db.query(ContaRecorrente)
            .filter(
                ContaRecorrente.perfil_id == perfil_id,
                ContaRecorrente.data_inicio <= inicio_mes,
            )
            .order_by(ContaRecorrente.dia_vencimento, ContaRecorrente.descricao)
            .all()
        )

        valores_pagos = {}
        if contas:
            pagamentos = (
                db.query(PagamentoConta.conta_id, Transacao.valor)
                .select_from(PagamentoConta)
                .join(Transacao, Transacao.id == PagamentoConta.transacao_id)
                .filter(
                    PagamentoConta.conta_id.in_([c.id for c in contas]),
                    PagamentoConta.mes == mes,
                    PagamentoConta.ano == ano,
                )
                .all()
            )
            valores_pagos = {conta_id: valor for conta_id, valor in pagamentos}

        resultado = []
        for c in contas:
            numero = numero_parcela(
                c.data_inicio, c.parcela_inicial, c.total_parcelas, ano, mes
            )
            if numero is None:  # parcelamento já terminou antes deste mês
                continue
            pago = c.id in valores_pagos
            resultado.append(
                {
                    "id": c.id,
                    "total_parcelas": c.total_parcelas,
                    "numero_parcela": numero if c.total_parcelas else None,
                    "descricao": c.descricao,
                    "valor": c.valor,
                    "dia_vencimento": c.dia_vencimento,
                    "forma_pagamento": c.forma_pagamento,
                    "vencimento": data_vencimento_no_mes(ano, mes, c.dia_vencimento),
                    "pago": pago,
                    # se já foi paga, vale o valor efetivamente lançado
                    "valor_efetivo": valores_pagos[c.id] if pago else c.valor,
                }
            )
        return resultado


def salvar_conta_recorrente(
    descricao: str,
    valor: float,
    dia_vencimento: int,
    forma_pagamento: str,
    perfil_id: int,
    mes_inicio: int,
    ano_inicio: int,
    conta_id: int = None,
    total_parcelas: int = None,
    parcela_mes: int = 1,
    data_inicio: date = None,
    reajuste: bool = False,
):
    """
    Cria uma conta recorrente ou, se 'conta_id' for informado, atualiza a existente.

    - Quando 'total_parcelas' é informado (e não é reajuste de valor unitário):
      'valor' é tratado como o valor total do parcelamento e dividido pelo número de parcelas.
    - Quando 'total_parcelas' é None: 'valor' é o valor mensal recorrente.
    """
    valor_float = float(valor)
    if valor_float <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    if not 1 <= int(dia_vencimento) <= 31:
        raise ValueError("O dia de vencimento deve estar entre 1 e 31.")

    if total_parcelas is not None:
        total_parcelas = int(total_parcelas)
        if total_parcelas < 1:
            raise ValueError("O número de parcelas deve ser pelo menos 1.")
        parcela_mes = int(parcela_mes or 1)
        if not 1 <= parcela_mes <= total_parcelas:
            raise ValueError(f"A parcela deste mês deve estar entre 1 e {total_parcelas}.")
    else:
        parcela_mes = 1

    # Se houver parcelamento e não for um reajuste avulso do valor da parcela,
    # divide o valor total informado pelo total de parcelas.
    if total_parcelas is not None and not reajuste:
        valor_parcela = _dividir_centavos(valor_float, total_parcelas)[0]
    else:
        valor_parcela = valor_float

    data_ancora = data_inicio or date(ano_inicio, mes_inicio, 1)

    with obter_sessao() as db:
        if conta_id:
            conta = (
                db.query(ContaRecorrente)
                .filter(
                    ContaRecorrente.id == conta_id,
                    ContaRecorrente.perfil_id == perfil_id,
                )
                .first()
            )
            if not conta:
                raise ValueError("Conta não encontrada para este perfil.")

            if data_inicio is not None:
                conta.data_inicio = data_inicio

            parcela_inicial = 1
            if total_parcelas is not None:
                parcela_inicial = calcular_parcela_inicial(
                    conta.data_inicio, parcela_mes, ano_inicio, mes_inicio
                )
                if parcela_inicial < 1:
                    raise ValueError(
                        "Essa parcela é anterior ao início da conta; confira o mês selecionado."
                    )

            conta.descricao = descricao
            conta.valor = valor_parcela
            conta.dia_vencimento = int(dia_vencimento)
            conta.forma_pagamento = forma_pagamento
            conta.total_parcelas = total_parcelas
            conta.parcela_inicial = parcela_inicial
        else:
            db.add(
                ContaRecorrente(
                    perfil_id=perfil_id,
                    descricao=descricao,
                    valor=valor_parcela,
                    dia_vencimento=int(dia_vencimento),
                    forma_pagamento=forma_pagamento,
                    data_inicio=data_ancora,
                    total_parcelas=total_parcelas,
                    parcela_inicial=parcela_mes,
                )
            )
        db.commit()


def remover_conta_recorrente(conta_id: int) -> bool:
    """
    Remove a conta recorrente (e os registros de pagamento dela). Os lançamentos
    já criados em 'transacoes' quando ela foi paga permanecem no histórico.
    """
    with obter_sessao() as db:
        conta = db.query(ContaRecorrente).filter(ContaRecorrente.id == conta_id).first()
        if conta:
            db.delete(conta)
            db.commit()
            return True
        return False


def alternar_pagamento_conta(conta_id: int, mes: int, ano: int, pago: bool) -> bool:
    """
    Marca/desmarca uma conta recorrente como paga em um mês.

    - Pago: cria uma Transacao de saída no dia do vencimento e registra o pagamento.
    - Desmarcado: apaga o registro de pagamento e a transação que ele gerou.
    """
    with obter_sessao() as db:
        conta = db.query(ContaRecorrente).filter(ContaRecorrente.id == conta_id).first()
        if not conta:
            return False

        pagamento = (
            db.query(PagamentoConta)
            .filter(
                PagamentoConta.conta_id == conta_id,
                PagamentoConta.mes == mes,
                PagamentoConta.ano == ano,
            )
            .first()
        )

        if pago and not pagamento:
            descricao_lancamento = conta.descricao
            valor_lancamento = conta.valor

            if conta.total_parcelas:
                numero = numero_parcela(
                    conta.data_inicio, conta.parcela_inicial, conta.total_parcelas, ano, mes
                )
                if numero is not None:
                    descricao_lancamento = f"{conta.descricao} ({numero}/{conta.total_parcelas})"
                    # Se o valor total original foi dividido em parcelas, ajusta o resto
                    # de centavos na última parcela para manter o total exato.
                    valor_total_estimado = round(conta.valor * conta.total_parcelas, 2)
                    parcelas_divididas = _dividir_centavos(valor_total_estimado, conta.total_parcelas)
                    if 1 <= numero <= len(parcelas_divididas):
                        valor_lancamento = parcelas_divididas[numero - 1]

            transacao = Transacao(
                descricao=descricao_lancamento,
                valor=valor_lancamento,
                tipo="Saída",
                forma_pagamento=conta.forma_pagamento,
                data=data_vencimento_no_mes(ano, mes, conta.dia_vencimento),
                perfil_id=conta.perfil_id,
                pago=True,
            )
            db.add(transacao)
            db.flush()  # gera o id da transação
            db.add(
                PagamentoConta(
                    conta_id=conta_id, mes=mes, ano=ano, transacao_id=transacao.id
                )
            )
        elif not pago and pagamento:
            transacao_id = pagamento.transacao_id
            db.delete(pagamento)
            db.flush()
            db.query(Transacao).filter(Transacao.id == transacao_id).delete()

        db.commit()
        return True