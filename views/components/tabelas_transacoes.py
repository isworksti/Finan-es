import flet as ft


def gerar_linhas_tabela(
    transacoes,
    abrir_edicao_cb,
    deletar_acao_cb,
    extrair_data_func,
    formatar_moeda_func,
    modo_cartao=False,
    mapa_cartoes=None,
    on_mudar_status_pago_cb=None,
):
    """Gera as linhas DataRow para a DataTable de lançamentos gerais ou cartões."""
    linhas = []
    mapa_c = mapa_cartoes or {}

    for t in transacoes:
        btn_edit = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            icon_color=ft.Colors.BLUE_400,
            tooltip="Editar",
            on_click=lambda e, trans=t: abrir_edicao_cb(trans),
        )
        btn_del = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINED,
            icon_color=ft.Colors.GREY_500,
            tooltip="Apagar",
            on_click=lambda e, t_id=t.id: deletar_acao_cb(t_id),
        )

        t_data = extrair_data_func(t)
        data_fmt = t_data.strftime("%d/%m/%Y") if t_data else "-"
        cor_val = (
            ft.Colors.GREEN_400 if t.tipo == "Entrada" else ft.Colors.RED_400
        )
        eh_saida = (getattr(t, "tipo", "Saída") == "Saída")

        # Checkbox "Pago?" apenas para "Saída" (e contas recorrentes)
        if eh_saida:
            controle_pago = ft.Checkbox(
                value=bool(getattr(t, "pago", True)),
                on_change=lambda e, t_id=t.id: on_mudar_status_pago_cb(t_id, e.control.value) if on_mudar_status_pago_cb else None,
                tooltip="Pago?",
            )
        else:
            controle_pago = ft.Text("—", color=ft.Colors.GREY_500)

        cells = [
            ft.DataCell(ft.Text(data_fmt)),
            ft.DataCell(ft.Text(t.descricao)),
            ft.DataCell(ft.Text(t.tipo)),
        ]

        # Adiciona a coluna do checkbox apenas na tabela geral (não de cartões)
        if not modo_cartao:
            cells.append(ft.DataCell(controle_pago))

        if modo_cartao:
            nome_c = "-"
            if hasattr(t, "cartao") and t.cartao:
                nome_c = t.cartao.nome
            elif getattr(t, "cartao_id", None) in mapa_c:
                nome_c = mapa_c[t.cartao_id].nome
            elif getattr(t, "cartao_id", None):
                nome_c = f"Cartão #{t.cartao_id}"
            cells.append(ft.DataCell(ft.Text(nome_c)))
        else:
            cells.append(ft.DataCell(ft.Text(t.forma_pagamento or "-")))

        cells.extend(
            [
                ft.DataCell(
                    ft.Text(formatar_moeda_func(t.valor), color=cor_val)
                ),
                ft.DataCell(ft.Row([btn_edit, btn_del], spacing=0)),
            ]
        )
        linhas.append(ft.DataRow(cells=cells))

    return linhas