"""Regras puras (sem banco de dados) das contas recorrentes."""
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta


def data_vencimento_no_mes(ano: int, mes: int, dia: int) -> date:
    """
    Data de vencimento de uma conta no mês/ano informado.
    Dias 29, 30 ou 31 viram o último dia do mês quando ele não existe (ex.: dia 31 em fevereiro).
    """
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, max(1, min(int(dia), ultimo_dia)))


def calcular_renda_comprometida(renda: float, total_pagas: float, total_pendentes: float) -> dict:
    """
    Quanto da renda do mês está comprometido com contas recorrentes.

- total_contas: contas pagas + contas a pagar do mês (o "valor" comprometido)
- livre: o que sobra da renda depois das contas (nunca negativo)
- percentual: total_contas / renda em % (None quando não há renda lançada)
    """
    total_contas = total_pagas + total_pendentes
    return {
        "renda": renda,
        "pagas": total_pagas,
        "pendentes": total_pendentes,
        "total_contas": total_contas,
        "livre": max(0.0, renda - total_contas),
        "percentual": (total_contas / renda * 100.0) if renda > 0 else None,
    }


def meses_desde(data_inicio: date, ano: int, mes: int) -> int:
    """
    Quantos meses se passaram entre a data de inserção/início da conta e o mês/ano informado.
    Usa relativedelta como âncora temporal.
    """
    ancora = date(data_inicio.year, data_inicio.month, 1)
    alvo = date(ano, mes, 1)
    delta = relativedelta(alvo, ancora)
    return delta.years * 12 + delta.months


def numero_parcela(data_inicio: date, parcela_inicial, total_parcelas, ano: int, mes: int):
    """
    Número da parcela da conta no mês/ano, ou None se a conta ainda não começou
    ou o parcelamento já terminou. Conta sem prazo (total_parcelas vazio) nunca termina.
    """
    indice = meses_desde(data_inicio, ano, mes)
    if indice < 0:
        return None
    numero = (parcela_inicial or 1) + indice
    if total_parcelas and numero > total_parcelas:
        return None
    return numero


def parcelas_restantes(numero, total_parcelas, pago: bool) -> int:
    """Quantas parcelas ainda faltam pagar (a do mês só conta se ainda não foi paga)."""
    if not total_parcelas or numero is None:
        return 0
    return max(0, total_parcelas - numero + (0 if pago else 1))


def calcular_parcela_inicial(data_inicio: date, parcela_mes: int, ano: int, mes: int) -> int:
    """
    Número da parcela no mês de inserção/início da conta, sabendo que 'parcela_mes' é o número
    da parcela no mês/ano informado.
    """
    return parcela_mes - meses_desde(data_inicio, ano, mes)

def projetar_competencias(
    data_inicio: date,
    dia_vencimento: int,
    valor: float,
    parcela_inicial: int = 1,
    total_parcelas: int | None = None,
    meses_a_frente: int = 12,
) -> list[dict]:
    """
    Projeta competências mensais a partir da data de inserção (âncora) usando relativedelta.
    """
    projecao = []
    base = date(data_inicio.year, data_inicio.month, 1)
    for offset in range(max(0, meses_a_frente)):
        ref = base + relativedelta(months=offset)
        num = numero_parcela(data_inicio, parcela_inicial, total_parcelas, ref.year, ref.month)
        if total_parcelas and num is None:
            break
        projecao.append(
            {
                "ano": ref.year,
                "mes": ref.month,
                "vencimento": data_vencimento_no_mes(ref.year, ref.month, dia_vencimento),
                "parcela": num,
                "total_parcelas": total_parcelas,
                "valor": valor,
            }
        )
    return projecao
