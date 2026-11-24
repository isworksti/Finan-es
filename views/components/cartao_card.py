from datetime import date
import flet as ft
import flet_charts as fch
from services.fatura_service import obter_data_vencimento_fatura


def criar_card_cartao(
    page_ref: ft.Page,
    cartao,
    mes_sel: int,
    ano_sel: int,
    transacoes_todas: list,
    mapa_cartoes: dict,
    on_atualizar_dados,
    formatar_moeda_func,
    mostrar_mensagem_func,
    obter_ou_criar_fatura_mensal_func,
    atualizar_status_fatura_func,
    calcular_limites_cartao_func,
    projetar_faturas_futuras_func,
    obter_mes_ano_fatura_func,
    MESES_LISTA,
):
    """Constrói o card individual estilizado para um cartão de crédito específico."""

    dia_fechamento = getattr(cartao, "dia_fechamento", None)
    dia_vencimento = getattr(cartao, "dia_vencimento", None)

    # Transações exclusivas da fatura do mês/ano filtrado (sem somatório de meses anteriores)
    tc_cartao_atual = []
    for tc in transacoes_todas:
        pertence_cartao = getattr(tc, "cartao_id", None) == cartao.id or (
            hasattr(tc, "cartao") and tc.cartao and tc.cartao.id == cartao.id
        )
        if not pertence_cartao:
            continue

        tc_dt = getattr(tc, "data", None) or getattr(tc, "data_dt", None)
        if not tc_dt:
            continue

        mes_fatura, ano_fatura = obter_mes_ano_fatura_func(
            tc_dt, dia_fechamento, getattr(tc, "tipo", "Saída")
        )
        if mes_fatura == mes_sel and ano_fatura == ano_sel:
            tc_cartao_atual.append(tc)

    data_reg_cartao = (
        getattr(cartao, "data_cadastro", None)
        or getattr(cartao, "data_registro", None)
        or getattr(cartao, "criado_em", None)
    )
    try:
        fatura_mensal = obter_ou_criar_fatura_mensal_func(
            cartao.id, mes_sel, ano_sel, data_registro=data_reg_cartao
        )
    except TypeError:
        fatura_mensal = obter_ou_criar_fatura_mensal_func(cartao.id, mes_sel, ano_sel)

    hoje = date.today()
    status_banco = getattr(fatura_mensal, "status", "Aberta")
    valor_pago_registrado = float(getattr(fatura_mensal, "valor_pago", 0.0) or 0.0)

    # Verifica se o ciclo/vencimento da fatura já passou em relação à data de hoje
    dt_venc_fatura = obter_data_vencimento_fatura(mes_sel, ano_sel, dia_vencimento)
    ja_passou_ciclo = False
    if (ano_sel, mes_sel) < (hoje.year, hoje.month):
        ja_passou_ciclo = True
    elif (ano_sel, mes_sel) == (hoje.year, hoje.month):
        if dt_venc_fatura and hoje > dt_venc_fatura:
            ja_passou_ciclo = True
        elif dia_fechamento and hoje.day > int(dia_fechamento):
            ja_passou_ciclo = True

    if status_banco == "Paga":
        status_atual = "Paga"
    elif ja_passou_ciclo:
        status_atual = "Fechada"
    else:
        status_atual = status_banco

    compras_cartao = sum(float(tc.valor) for tc in tc_cartao_atual if tc.tipo == "Saída")
    entradas_cartao = sum(float(tc.valor) for tc in tc_cartao_atual if tc.tipo == "Entrada")

    # Abatimento considera entradas da fatura + valor_pago registrado (ou total da fatura se marcada como Paga)
    saldo_bruto = max(0.0, compras_cartao - entradas_cartao)
    if status_atual == "Paga":
        abatimento_visual = max(entradas_cartao + valor_pago_registrado, compras_cartao)
        fatura_cartao = 0.0
    else:
        abatimento_visual = entradas_cartao + valor_pago_registrado
        fatura_cartao = max(0.0, saldo_bruto - valor_pago_registrado)

    lims_cartao = calcular_limites_cartao_func(cartao.id)
    t_total = lims_cartao["total"]
    t_comp = lims_cartao["comprometido"]
    t_disp = lims_cartao["disponivel"]

    perc_c = (t_comp / t_total) if t_total > 0 else 0.0
    cor_c = (
        ft.Colors.GREEN_400
        if perc_c < 0.7
        else (ft.Colors.AMBER_400 if perc_c < 0.9 else ft.Colors.RED_400)
    )

    chart_indiv = fch.PieChart(
        sections=[
            fch.PieChartSection(
                value=fatura_cartao if fatura_cartao > 0 else 0.001,
                title=f"A pagar\n{formatar_moeda_func(fatura_cartao)}",
                color=ft.Colors.RED_400,
                radius=28,
                title_style=ft.TextStyle(size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ),
            fch.PieChartSection(
                value=abatimento_visual if abatimento_visual > 0 else 0.001,
                title=f"Abatido\n{formatar_moeda_func(abatimento_visual)}",
                color=ft.Colors.GREEN_400,
                radius=28,
                title_style=ft.TextStyle(size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ),
        ]
        if (fatura_cartao > 0 or abatimento_visual > 0)
        else [
            fch.PieChartSection(
                value=1.0,
                title="Sem gastos",
                color=ft.Colors.GREY_700,
                radius=28,
                title_style=ft.TextStyle(size=8, color=ft.Colors.WHITE),
            )
        ],
        sections_space=2,
        center_space_radius=18,
    )

    cor_status = (
        ft.Colors.GREEN_400
        if status_atual == "Paga"
        else (ft.Colors.AMBER_400 if status_atual == "Fechada" else ft.Colors.BLUE_300)
    )

    texto_status = ft.Text(
        status_atual,
        size=11,
        weight=ft.FontWeight.BOLD,
        color=cor_status,
    )

    def pagar_fatura_acao(e):
        if fatura_cartao <= 0 and status_atual == "Paga":
            mostrar_mensagem_func(page_ref, "ℹ️ Esta fatura já está paga.")
            return
        if fatura_cartao <= 0 and compras_cartao <= 0:
            mostrar_mensagem_func(page_ref, "⚠️ Esta fatura não possui saldo devedor.")
            return

        valor_a_abater = fatura_cartao if fatura_cartao > 0 else saldo_bruto
        novo_valor_pago = valor_pago_registrado + valor_a_abater
        try:
            atualizar_status_fatura_func(
                cartao.id, mes_sel, ano_sel, "Paga", valor_pago=novo_valor_pago
            )
        except TypeError:
            atualizar_status_fatura_func(cartao.id, mes_sel, ano_sel, "Paga")

        mostrar_mensagem_func(
            page_ref,
            f"✅ Abatimento de {formatar_moeda_func(valor_a_abater)} contabilizado e fatura marcada como Paga!",
        )
        on_atualizar_dados()

    btn_pagar = ft.FilledButton(
        "Pagar",
        icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
        icon_color=ft.Colors.GREEN_400,
        scale=0.85,
        on_click=pagar_fatura_acao,
    )

    # Projeção a partir do mês filtrado + 3 meses à frente (4 meses no total a partir do filtro)
    try:
        projecoes = projetar_faturas_futuras_func(
            transacoes_todas,
            cartao.id,
            qtd_meses=4,
            mes_base=mes_sel,
            ano_base=ano_sel,
            dia_fechamento=dia_fechamento,
        )
    except TypeError:
        projecoes = projetar_faturas_futuras_func(transacoes_todas, cartao.id, qtd_meses=4)

    linhas_projecao = []
    for (ano_p, mes_p), val_p in projecoes.items():
        nome_m = (
            MESES_LISTA[mes_p - 1][1]
            if isinstance(MESES_LISTA[mes_p - 1], tuple)
            else str(MESES_LISTA[mes_p - 1])
        )
        dt_venc = obter_data_vencimento_fatura(mes_p, ano_p, dia_vencimento)
        sufixo_venc = f" (venc. {dt_venc.strftime('%d/%m')})" if dt_venc else ""
        linhas_projecao.append(
            ft.Row(
                [
                    ft.Text(f"{nome_m}", size=10, color=ft.Colors.GREY_300),
                    ft.Text(
                        formatar_moeda_func(val_p),
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_300,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )

    bloco_projecao = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "Projeção de Futuras Faturas ",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLUE_200,
                ),
                ft.Column(linhas_projecao, spacing=2),
            ],
            spacing=4,
        ),
        padding=8,
        bgcolor=ft.Colors.WHITE_10,
        border_radius=6,
    )

    info_ciclo = []
    if dia_fechamento:
        info_ciclo.append(f"Fecha dia {dia_fechamento}")
    if dia_vencimento:
        info_ciclo.append(f"Vence dia {dia_vencimento}")
    texto_ciclo = " · ".join(info_ciclo)

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(f"Cartão: {cartao.nome}", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"Fatura: {formatar_moeda_func(fatura_cartao)}",
                            size=12,
                            color=ft.Colors.AMBER_400,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                *(
                    [ft.Text(texto_ciclo, size=10, color=ft.Colors.GREY_400)]
                    if texto_ciclo
                    else []
                ),
                ft.Row(
                    [
                        ft.Text("Status:", size=11, color=ft.Colors.GREY_300),
                        texto_status,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=chart_indiv,
                    width=290,
                    height=110,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Divider(height=1, color=ft.Colors.WHITE_12),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    f"Limite ({perc_c * 100:.1f}% usado)",
                                    size=11,
                                    color=ft.Colors.GREY_300,
                                ),
                                ft.Text(
                                    f"Total: {formatar_moeda_func(t_total)}",
                                    size=11,
                                    color=ft.Colors.GREY_400,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ProgressBar(
                            value=min(1.0, perc_c),
                            color=cor_c,
                            bgcolor=ft.Colors.WHITE_10,
                            height=6,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    f"Disp: {formatar_moeda_func(t_disp)}",
                                    color=ft.Colors.GREEN_400,
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"Usado: {formatar_moeda_func(t_comp)}",
                                    color=ft.Colors.RED_400,
                                    size=10,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=3,
                ),
                ft.Divider(height=1, color=ft.Colors.WHITE_12),
                bloco_projecao,
                ft.Row([btn_pagar], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=6,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.WHITE_24),
        border_radius=10,
        width=320,
    )