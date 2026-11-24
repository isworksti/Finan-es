from database.crud import (
    buscar_cartoes_do_perfil,
    buscar_transacoes_do_perfil,
    obter_contas_do_mes,
)
from services.contas_service import calcular_renda_comprometida
from services.fatura_service import obter_mes_ano_fatura


class DashboardController:
    def __init__(self, perfil_ativo_id):
        self.perfil_ativo_id = perfil_ativo_id

    def obter_dados_filtrados(self, mes_sel: int, ano_sel: int, texto_busca: str = "", forma_sel: str = "Todas"):
        """Busca, processa e filtra transações, cartões e KPIs do perfil ativo."""
        if not self.perfil_ativo_id[0]:
            return None

        perfil_id = self.perfil_ativo_id[0]
        cartoes_lista = buscar_cartoes_do_perfil(perfil_id)
        mapa_cartoes = {c.id: c for c in cartoes_lista}
        transacoes_todas = buscar_transacoes_do_perfil(perfil_id)

        # 1. Filtro de Lançamentos Gerais
        transacoes_mes = []
        for t in transacoes_todas:
            is_cred = (
                str(getattr(t, "forma_pagamento", "")).strip().lower() in ["crédito", "credito"]
                or getattr(t, "cartao_id", None) is not None
            )
            if is_cred:
                continue

            dt = getattr(t, "data", None) or getattr(t, "data_dt", None)
            if not dt or dt.month != mes_sel or dt.year != ano_sel:
                continue

            transacoes_mes.append(t)

        total_entradas = sum(t.valor for t in transacoes_mes if t.tipo == "Entrada" and getattr(t, "pago", True))
        total_saidas = sum(t.valor for t in transacoes_mes if t.tipo == "Saída" and getattr(t, "pago", True))
        saldo_mes = total_entradas - total_saidas

        # 2. Filtro de Transações de Cartão de Crédito no Mês
        tc_mes = []
        for t in transacoes_todas:
            is_cred = getattr(t, "forma_pagamento", "") == "Crédito" or getattr(t, "cartao_id", None) is not None
            if is_cred:
                t_dt = getattr(t, "data", None) or getattr(t, "data_dt", None)
                if not t_dt:
                    continue

                dia_fechamento = None
                if hasattr(t, "cartao") and t.cartao:
                    dia_fechamento = t.cartao.dia_fechamento
                elif getattr(t, "cartao_id", None) in mapa_cartoes:
                    dia_fechamento = mapa_cartoes[t.cartao_id].dia_fechamento

                mes_fatura, ano_fatura = obter_mes_ano_fatura(t_dt, dia_fechamento, t.tipo)

                if mes_fatura == mes_sel and ano_fatura == ano_sel:
                    if texto_busca and texto_busca not in str(t.descricao).lower():
                        continue
                    tc_mes.append(t)

        compras_cartao_mes = sum(tc.valor for tc in tc_mes if tc.tipo == "Saída")
        pagamentos_cartao_mes = sum(tc.valor for tc in tc_mes if tc.tipo == "Entrada")
        fatura_mes_total = max(0.0, compras_cartao_mes - pagamentos_cartao_mes)

        # 3. Contas recorrentes e renda comprometida do mês
        # (a renda considera todas as entradas pagas do mês, sem os filtros de busca/forma)
        contas_mes = obter_contas_do_mes(perfil_id, mes_sel, ano_sel)
        total_contas_pagas = sum(c["valor_efetivo"] for c in contas_mes if c["pago"])
        total_contas_pendentes = sum(c["valor"] for c in contas_mes if not c["pago"])

        renda_mes = 0.0
        for t in transacoes_todas:
            dt = getattr(t, "data", None) or getattr(t, "data_dt", None)
            if (
                dt
                and dt.month == mes_sel
                and dt.year == ano_sel
                and t.tipo == "Entrada"
                and getattr(t, "pago", True)
            ):
                renda_mes += t.valor

        comprometimento = calcular_renda_comprometida(
            renda_mes, total_contas_pagas, total_contas_pendentes
        )

        return {
            "cartoes_lista": cartoes_lista,
            "mapa_cartoes": mapa_cartoes,
            "transacoes_todas": transacoes_todas,
            "transacoes_mes": transacoes_mes,
            "tc_mes": tc_mes,
            "total_entradas": total_entradas,
            "total_saidas": total_saidas,
            "saldo_mes": saldo_mes,
            "fatura_mes_total": fatura_mes_total,
            "contas_mes": contas_mes,
            "comprometimento": comprometimento,
        }