import calendar
from datetime import date
from dateutil.relativedelta import relativedelta


def obter_mes_ano_fatura(data_transacao: date, dia_fechamento: int = None, tipo: str = "Saída"):
    """
    Calcula em qual mês/ano de fatura a transação irá cair com base
    no dia de fechamento do cartão.

    REGRA ÚNICA do app: compras feitas até o dia de fechamento (inclusive)
    entram na fatura do próprio mês; compras feitas depois do dia de
    fechamento entram na fatura do mês seguinte.
    """
    if not dia_fechamento:
        return data_transacao.month, data_transacao.year

    if data_transacao.day > dia_fechamento:
        data_fatura = data_transacao + relativedelta(months=1)
    else:
        data_fatura = data_transacao

    return data_fatura.month, data_fatura.year


def obter_data_vencimento_fatura(mes: int, ano: int, dia_vencimento: int | None) -> date | None:
    """Retorna a data de vencimento da fatura para o mês/ano informado."""
    if not dia_vencimento:
        return None
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, max(1, min(int(dia_vencimento), ultimo_dia)))


def filtrar_transacoes_fatura(transacoes, mes_alvo, ano_alvo, dia_fechamento=None):
    """
    Filtra as transações que pertencem a uma fatura específica (mês/ano)
    considerando o dia de fechamento do cartão.
    """
    filtradas = []
    for t in transacoes:
        t_dt = getattr(t, "data", None) or getattr(t, "data_dt", None)
        if not t_dt:
            continue

        m_fat, a_fat = obter_mes_ano_fatura(t_dt, dia_fechamento, getattr(t, "tipo", "Saída"))
        if m_fat == mes_alvo and a_fat == ano_alvo:
            filtradas.append(t)

    return filtradas


def projetar_faturas_futuras(
    transacoes_do_perfil,
    cartao_id,
    qtd_meses=3,
    mes_base: int | None = None,
    ano_base: int | None = None,
    dia_fechamento: int | None = None,
):
    """
    Projeta o valor individual de cada fatura a partir do mês/ano filtrado
    (ou do mês atual se não informado) por `qtd_meses` à frente, sem acumular
    saldos de meses anteriores.
    Retorna um dicionário ordenado com chaves (ano, mes) e valores de cada mês.
    """
    hoje = date.today()
    inicio = date(
        ano_base if ano_base else hoje.year,
        mes_base if mes_base else hoje.month,
        1,
    )
    projecoes = {}

    for i in range(max(1, qtd_meses)):
        mes_alvo = inicio + relativedelta(months=i)
        projecoes[(mes_alvo.year, mes_alvo.month)] = 0.0

    for t in transacoes_do_perfil:
        c_id = getattr(t, "cartao_id", None)
        if c_id != cartao_id:
            continue

        t_dt = getattr(t, "data", None) or getattr(t, "data_dt", None)
        if not t_dt:
            continue

        total_parcelas = max(1, getattr(t, "parcelas", 1) or 1)
        valor_parcela = float(t.valor) / total_parcelas

        for p in range(total_parcelas):
            data_parcela_base = t_dt + relativedelta(months=p)
            ano_fat, mes_fat = (
                obter_mes_ano_fatura(data_parcela_base, dia_fechamento, getattr(t, "tipo", "Saída"))[::-1]
            )
            chave = (ano_fat, mes_fat)
            if chave in projecoes:
                if t.tipo == "Saída":
                    projecoes[chave] += valor_parcela
                elif t.tipo == "Entrada":
                    projecoes[chave] -= valor_parcela

    for chave, valor in projecoes.items():
        projecoes[chave] = max(0.0, valor)

    return projecoes


def calcular_comprometido(transacoes, dia_fechamento=None, faturas_pagas=None) -> float:
    """
    Valor do limite do cartão que ainda está comprometido.
    """
    pagas = set(faturas_pagas or [])
    compras = 0.0
    abatimentos = 0.0

    for t in transacoes:
        t_dt = getattr(t, "data", None) or getattr(t, "data_dt", None)
        if t_dt and pagas:
            fatura = obter_mes_ano_fatura(t_dt, dia_fechamento, getattr(t, "tipo", "Saída"))
            if fatura in pagas:
                continue

        if t.tipo == "Saída":
            compras += float(t.valor)
        elif t.tipo == "Entrada":
            abatimentos += float(t.valor)

    return max(0.0, compras - abatimentos)