from datetime import date, datetime
import flet as ft
import flet_charts as fch
from database.crud import (
    MAPA_MESES,
    MESES,
    buscar_todos_perfis,
    buscar_transacoes_do_perfil,
    eh_credito,
    remover_transacao,
    salvar_transacao,
    atualizar_transacao,
)
from utils.date_utils import extrair_data
from utils.ui_helpers import mostrar_mensagem


class DashboardView(ft.Column):
    def __init__(self, page: ft.Page, perfil_ativo_id, on_trocar_perfil):
        super().__init__(expand=True, visible=False)
        self.page_ref = page
        self.perfil_ativo_id = perfil_ativo_id
        self.on_trocar_perfil_cb = on_trocar_perfil
        self.detalhes_fatias = {}
        self.transacao_em_edicao_id = None

        # --- COMPONENTES DE FILTRO E FORMULÁRIO ---
        self.txt_data = ft.TextField(
            label="Dia",
            value=f"{date.today().day:02d}",
            width=70,
            hint_text="DD",
        )

        self.dropdown_filtro_mes = ft.Dropdown(
            label="Mês da Fatura",
            width=150,
            value=str(datetime.now().month),
            options=[ft.dropdown.Option(key=m[0], text=m[1]) for m in MESES],
            on_select=self.ao_filtrar_data,
        )

        self.dropdown_filtro_ano = ft.Dropdown(
            label="Ano",
            width=110,
            value=str(datetime.now().year),
            options=[
                ft.dropdown.Option(key=str(ano), text=str(ano))
                for ano in range(2024, 2028)
            ],
            on_select=self.ao_filtrar_data,
        )

        self.dropdown_perfis_header = ft.Dropdown(
            label="Perfil Ativo",
            width=160,
            options=[],
            on_select=self.ao_mudar_perfil_header,
        )

        self.txt_descricao = ft.TextField(
            label="Descrição", expand=True, on_submit=self.adicionar_transacao
        )
        self.txt_valor = ft.TextField(
            label="Valor (R$)",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            on_submit=self.adicionar_transacao,
        )

        self.dropdown_tipo = ft.Dropdown(
            label="Tipo",
            width=110,
            options=[ft.dropdown.Option("Entrada"), ft.dropdown.Option("Saída")],
            value="Saída",
        )

        self.dropdown_pagamento = ft.Dropdown(
            label="Pagamento",
            width=130,
            options=[
                ft.dropdown.Option("Dinheiro"),
                ft.dropdown.Option("PIX"),
                ft.dropdown.Option("Crédito"),
                ft.dropdown.Option("Débito"),
            ],
            value="PIX",
        )

        self.btn_salvar = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD, color=ft.Colors.WHITE),
                    ft.Text("Adicionar", color=ft.Colors.WHITE),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.BLUE_600,
            padding=10,
            border_radius=8,
            on_click=self.adicionar_transacao,
        )

        # --- COMPONENTES DO MODAL DE EDIÇÃO ---
        self.edit_txt_dia = ft.TextField(label="Dia", width=70, hint_text="DD")
        self.edit_txt_mes = ft.TextField(label="Mês", width=70, hint_text="MM")
        self.edit_txt_ano = ft.TextField(label="Ano", width=90, hint_text="AAAA")
        self.edit_txt_descricao = ft.TextField(label="Descrição", expand=True)
        self.edit_txt_valor = ft.TextField(
            label="Valor (R$)", keyboard_type=ft.KeyboardType.NUMBER, width=120
        )
        self.edit_dropdown_tipo = ft.Dropdown(
            label="Tipo",
            width=110,
            options=[ft.dropdown.Option("Entrada"), ft.dropdown.Option("Saída")],
        )
        self.edit_dropdown_pagamento = ft.Dropdown(
            label="Pagamento",
            width=130,
            options=[
                ft.dropdown.Option("Dinheiro"),
                ft.dropdown.Option("PIX"),
                ft.dropdown.Option("Crédito"),
                ft.dropdown.Option("Débito"),
            ],
        )

        self.dialog_editar = ft.AlertDialog(
            title=ft.Text("Editar Lançamento"),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self.edit_txt_dia,
                            self.edit_txt_mes,
                            self.edit_txt_ano,
                        ]
                    ),
                    self.edit_txt_descricao,
                    ft.Row(
                        [
                            self.edit_txt_valor,
                            self.edit_dropdown_tipo,
                            self.edit_dropdown_pagamento,
                        ]
                    ),
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=self.fechar_dialog_edicao),
                ft.FilledButton(
                    "Salvar Alterações",
                    bgcolor=ft.Colors.BLUE_600,
                    color=ft.Colors.WHITE,
                    on_click=self.salvar_edicao_transacao,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- CARTÕES DE INDICADORES (KPIs) ---
        self.txt_kpi_entradas = ft.Text("R$ 0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.txt_kpi_saidas = ft.Text("R$ 0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)
        self.txt_kpi_saldo = ft.Text("R$ 0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
        self.txt_fatura_total = ft.Text("R$ 0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)

        # --- GRÁFICOS ---
        self.txt_hover_detalhes = ft.Text(
            "Passe o mouse sobre as fatias do gráfico para ver os itens.",
            size=13,
            color=ft.Colors.GREY_400,
        )

        self.chart_geral = fch.PieChart(
            sections=[],
            sections_space=2,
            center_space_radius=45,
            expand=True,
            on_event=self.on_chart_hover,
        )

        self.chart_cartao = fch.PieChart(
            sections=[],
            sections_space=2,
            center_space_radius=45,
            expand=True,
        )

        # --- TABELAS ---
        self.tabela_geral = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Data")),
                ft.DataColumn(ft.Text("Descrição")),
                ft.DataColumn(ft.Text("Tipo")),
                ft.DataColumn(ft.Text("Pagamento")),
                ft.DataColumn(ft.Text("Valor (R$)")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            rows=[],
            expand=True,
        )

        self.tabela_cartao = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Data")),
                ft.DataColumn(ft.Text("Descrição")),
                ft.DataColumn(ft.Text("Tipo")),
                ft.DataColumn(ft.Text("Valor (R$)")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            rows=[],
            expand=True,
        )

        # --- CONSTRUÇÃO DAS ABAS ---
        self._construir_aba_dashboard()
        self._construir_aba_geral()
        self._construir_aba_cartao()

        # Botões das Abas
        self.btn_tab_dashboard = ft.OutlinedButton(
            "Dashboard",
            icon=ft.Icons.ANALYTICS_OUTLINED,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600),
            on_click=lambda e: self.mudar_aba("dashboard"),
        )
        self.btn_tab_geral = ft.OutlinedButton(
            "Lançamentos Gerais",
            icon=ft.Icons.TABLE_ROWS_OUTLINED,
            style=ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT),
            on_click=lambda e: self.mudar_aba("geral"),
        )
        self.btn_tab_cartao = ft.OutlinedButton(
            "Cartão de Crédito",
            icon=ft.Icons.CREDIT_CARD,
            style=ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT),
            on_click=lambda e: self.mudar_aba("cartao"),
        )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Painel Financeiro", size=24, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            ft.Text("Período:", weight=ft.FontWeight.BOLD),
                            self.dropdown_filtro_mes,
                            self.dropdown_filtro_ano,
                            ft.VerticalDivider(),
                            self.dropdown_perfis_header,
                            ft.TextButton(
                                "Trocar Perfil",
                                icon=ft.Icons.SWAP_HORIZ,
                                on_click=lambda e: self.on_trocar_perfil_cb(),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            margin=10,
        )

        self.controls = [
            header,
            ft.Row(
                [
                    self.txt_data,
                    self.txt_descricao,
                    self.txt_valor,
                    self.dropdown_tipo,
                    self.dropdown_pagamento,
                    self.btn_salvar,
                ]
            ),
            ft.Divider(),
            ft.Row(
                [self.btn_tab_dashboard, self.btn_tab_geral, self.btn_tab_cartao],
                spacing=10,
            ),
            ft.Stack(
                controls=[self.aba_dashboard, self.aba_geral, self.aba_cartao_content],
                expand=True,
            ),
        ]

    def _criar_card_kpi(self, titulo, controle_texto, icone, cor_icone):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icone, size=30, color=cor_icone),
                    ft.Column(
                        [
                            ft.Text(titulo, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_300),
                            controle_texto,
                        ],
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=15,
            bgcolor=ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, ft.Colors.WHITE_24),
            border_radius=10,
            expand=True,
        )

    def _construir_aba_dashboard(self):
        cards_kpi = ft.Row(
            [
                self._criar_card_kpi("Entradas no Mês", self.txt_kpi_entradas, ft.Icons.ARROW_UPWARD, ft.Colors.GREEN_400),
                self._criar_card_kpi("Saídas no Mês", self.txt_kpi_saidas, ft.Icons.ARROW_DOWNWARD, ft.Colors.RED_400),
                self._criar_card_kpi("Saldo Líquido", self.txt_kpi_saldo, ft.Icons.ACCOUNT_BALANCE_WALLET, ft.Colors.BLUE_400),
                self._criar_card_kpi("Fatura de Crédito", self.txt_fatura_total, ft.Icons.CREDIT_CARD, ft.Colors.AMBER_400),
            ],
            spacing=15,
        )

        box_grafico_geral = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Entradas x Saídas", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(content=self.chart_geral, height=220),
                    ft.Divider(),
                    ft.Text("Detalhes da Categoria:", weight=ft.FontWeight.BOLD, size=12),
                    self.txt_hover_detalhes,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=15,
            border=ft.Border.all(1, ft.Colors.WHITE_24),
            border_radius=10,
            expand=True,
        )

        box_grafico_cartao = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Fatura do Cartão", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(content=self.chart_cartao, height=220),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=15,
            border=ft.Border.all(1, ft.Colors.WHITE_24),
            border_radius=10,
            expand=True,
        )

        graficos_row = ft.Row([box_grafico_geral, box_grafico_cartao], spacing=15, expand=True)

        self.aba_dashboard = ft.Container(
            content=ft.Column([cards_kpi, ft.Container(height=10), graficos_row], expand=True),
            padding=10,
            visible=True,
            expand=True,
        )

    def _construir_aba_geral(self):
        self.aba_geral = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Histórico de Lançamentos Gerais", size=18, weight=ft.FontWeight.BOLD),
                    self.tabela_geral,
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
            visible=False,
            expand=True,
        )

    def _construir_aba_cartao(self):
        self.aba_cartao_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Lançamentos de Cartão de Crédito", size=18, weight=ft.FontWeight.BOLD),
                    self.tabela_cartao,
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
            visible=False,
            expand=True,
        )

    def abrir_dialog_edicao(self, transacao):
        self.transacao_em_edicao_id = transacao.id
        t_data = extrair_data(transacao)

        if t_data:
            self.edit_txt_dia.value = f"{t_data.day:02d}"
            self.edit_txt_mes.value = f"{t_data.month:02d}"
            self.edit_txt_ano.value = str(t_data.year)
        else:
            hoje = date.today()
            self.edit_txt_dia.value = f"{hoje.day:02d}"
            self.edit_txt_mes.value = f"{hoje.month:02d}"
            self.edit_txt_ano.value = str(hoje.year)

        self.edit_txt_descricao.value = transacao.descricao or ""
        self.edit_txt_valor.value = f"{transacao.valor:.2f}".replace(".", ",")
        self.edit_dropdown_tipo.value = transacao.tipo
        self.edit_dropdown_pagamento.value = transacao.forma_pagamento or "PIX"

        if self.dialog_editar not in self.page_ref.overlay:
            self.page_ref.overlay.append(self.dialog_editar)
            
        self.dialog_editar.open = True
        self.page_ref.update()

    def fechar_dialog_edicao(self, e=None):
        self.transacao_em_edicao_id = None
        self.dialog_editar.open = False
        self.page_ref.update()

    def salvar_edicao_transacao(self, e):
        if not self.transacao_em_edicao_id:
            return

        try:
            dia = int(self.edit_txt_dia.value.strip())
            mes = int(self.edit_txt_mes.value.strip())
            ano = int(self.edit_txt_ano.value.strip())
            nova_data = date(ano, mes, dia)
        except (ValueError, TypeError):
            mostrar_mensagem(self.page_ref, "❌ Erro: Data inválida para edição!")
            return

        try:
            novo_valor = float(self.edit_txt_valor.value.replace(",", "."))
        except (ValueError, TypeError):
            mostrar_mensagem(self.page_ref, "❌ Erro: Valor inválido!")
            return

        if not self.edit_txt_descricao.value.strip():
            mostrar_mensagem(self.page_ref, "❌ Erro: A descrição é obrigatória!")
            return

        try:
            atualizar_transacao(
                transacao_id=self.transacao_em_edicao_id,
                descricao=self.edit_txt_descricao.value.strip(),
                valor=novo_valor,
                tipo=self.edit_dropdown_tipo.value,
                forma_pagamento=self.edit_dropdown_pagamento.value,
                data_dt=nova_data,
            )
            self.fechar_dialog_edicao()
            mostrar_mensagem(self.page_ref, "✅ Lançamento atualizado com sucesso!")
            self.carregar_dados()
        except Exception as ex:
            print(f"Erro ao editar transação: {ex}")
            mostrar_mensagem(self.page_ref, "❌ Erro ao salvar edição no banco!")

    def on_chart_hover(self, e: fch.PieChartEvent):
        if (
            e.section_index is not None
            and e.section_index >= 0
            and e.section_index in self.detalhes_fatias
        ):
            self.txt_hover_detalhes.value = self.detalhes_fatias[e.section_index]
        else:
            self.txt_hover_detalhes.value = (
                "Passe o mouse sobre as fatias do gráfico para ver os itens."
            )
        self.txt_hover_detalhes.update()

    def carregar_perfis_header(self):
        perfis = buscar_todos_perfis()
        self.dropdown_perfis_header.options = [
            ft.dropdown.Option(key=str(p.id), text=p.nome) for p in perfis
        ]
        if self.perfil_ativo_id[0]:
            self.dropdown_perfis_header.value = str(self.perfil_ativo_id[0])

    def carregar_dados(self):
        if not self.perfil_ativo_id[0]:
            self.page_ref.update()
            return

        try:
            val_mes = self.dropdown_filtro_mes.value
            mes_sel = (
                int(val_mes)
                if str(val_mes).isdigit()
                else MAPA_MESES.get(str(val_mes), date.today().month)
            )

            try:
                ano_sel = int(self.dropdown_filtro_ano.value)
            except (TypeError, ValueError):
                ano_sel = date.today().year

            transacoes_todas = buscar_transacoes_do_perfil(self.perfil_ativo_id[0])

            transacoes_mes = []
            for t in transacoes_todas:
                t_data = extrair_data(t)
                if t_data and t_data.month == mes_sel and t_data.year == ano_sel:
                    transacoes_mes.append(t)

            total_entradas = 0.0
            total_saidas = 0.0
            novas_linhas_geral = []

            for t in transacoes_mes:
                if t.tipo == "Entrada":
                    total_entradas += t.valor
                    cor_val = ft.Colors.GREEN_400
                else:
                    total_saidas += t.valor
                    cor_val = ft.Colors.RED_400

                btn_edit = ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    tooltip="Editar",
                    on_click=lambda e, trans=t: self.abrir_dialog_edicao(trans),
                )

                btn_del = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINED,
                    icon_color=ft.Colors.GREY_500,
                    tooltip="Apagar",
                    on_click=lambda e, t_id=t.id: self.deletar_transacao_acao(t_id),
                )
                t_data_val = extrair_data(t)
                data_fmt = t_data_val.strftime("%d/%m/%Y") if t_data_val else "-"

                novas_linhas_geral.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(data_fmt)),
                            ft.DataCell(ft.Text(t.descricao)),
                            ft.DataCell(ft.Text(t.tipo)),
                            ft.DataCell(ft.Text(t.forma_pagamento or "-")),
                            ft.DataCell(ft.Text(f"R$ {t.valor:.2f}", color=cor_val)),
                            ft.DataCell(ft.Row([btn_edit, btn_del], spacing=0)),
                        ]
                    )
                )

            self.tabela_geral.rows = novas_linhas_geral

            saldo_mes = total_entradas - total_saidas
            self.txt_kpi_entradas.value = f"R$ {total_entradas:.2f}"
            self.txt_kpi_saidas.value = f"R$ {total_saidas:.2f}"
            self.txt_kpi_saldo.value = f"R$ {saldo_mes:.2f}"
            self.txt_kpi_saldo.color = ft.Colors.GREEN_400 if saldo_mes >= 0 else ft.Colors.RED_400

            self.detalhes_fatias.clear()
            entradas_mes = [t for t in transacoes_mes if t.tipo == "Entrada"]
            saidas_mes = [t for t in transacoes_mes if t.tipo == "Saída"]

            nomes_e = " ".join([f"R$ {i.valor:.2f} {i.descricao} \n" for i in entradas_mes])
            nomes_s = " ".join([f"R$ {i.valor:.2f} {i.descricao} \n" for i in saidas_mes])

            self.detalhes_fatias[0] = (
                f"🟢 Entradas ({len(entradas_mes)} itens):\n{nomes_e if nomes_e else 'Nenhum item'}"
            )
            self.detalhes_fatias[1] = (
                f"🔴 Saídas ({len(saidas_mes)} itens):\n{nomes_s if nomes_s else 'Nenhum item'}"
            )

            tot_geral = total_entradas + total_saidas
            novas_sec_geral = []
            if tot_geral > 0:
                pct_e = (total_entradas / tot_geral) * 100
                pct_s = (total_saidas / tot_geral) * 100
                novas_sec_geral = [
                    fch.PieChartSection(
                        value=total_entradas if total_entradas > 0 else 0.001,
                        title=f"Entradas\n{pct_e:.1f}%",
                        color=ft.Colors.BLUE_400,
                        radius=60,
                        title_style=ft.TextStyle(
                            size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                        ),
                    ),
                    fch.PieChartSection(
                        value=total_saidas if total_saidas > 0 else 0.001,
                        title=f"Saídas\n{pct_s:.1f}%",
                        color=ft.Colors.RED_400,
                        radius=60,
                        title_style=ft.TextStyle(
                            size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                        ),
                    ),
                ]
            self.chart_geral.sections = novas_sec_geral

            compras_mes_atual = 0.0
            pagamentos_mes_atual = 0.0
            novas_linhas_cartao = []

            transacoes_credito_mes = [
                t for t in transacoes_mes if eh_credito(t.forma_pagamento)
            ]

            for tc in transacoes_credito_mes:
                if tc.tipo == "Saída":
                    compras_mes_atual += tc.valor
                elif tc.tipo == "Entrada":
                    pagamentos_mes_atual += tc.valor

                btn_edit_cc = ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    tooltip="Editar",
                    on_click=lambda e, trans=tc: self.abrir_dialog_edicao(trans),
                )
                btn_del_cc = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINED,
                    icon_color=ft.Colors.GREY_500,
                    tooltip="Apagar",
                    on_click=lambda e, t_id=tc.id: self.deletar_transacao_acao(t_id),
                )
                tc_data_val = extrair_data(tc)
                data_fmt_cc = tc_data_val.strftime("%d/%m/%Y") if tc_data_val else "-"
                cor_cc = (
                    ft.Colors.GREEN_400 if tc.tipo == "Entrada" else ft.Colors.RED_400
                )

                novas_linhas_cartao.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(data_fmt_cc)),
                            ft.DataCell(ft.Text(tc.descricao)),
                            ft.DataCell(ft.Text(tc.tipo)),
                            ft.DataCell(ft.Text(f"R$ {tc.valor:.2f}", color=cor_cc)),
                            ft.DataCell(ft.Row([btn_edit_cc, btn_del_cc], spacing=0)),
                        ]
                    )
                )

            self.tabela_cartao.rows = novas_linhas_cartao

            transacoes_credito_todas = [
                t for t in transacoes_todas if eh_credito(t.forma_pagamento)
            ]
            transacoes_credito_todas.sort(
                key=lambda t: (extrair_data(t) or date.min, t.id or 0)
            )

            saldo_fatura = 0.0
            for tc in transacoes_credito_todas:
                tc_data = extrair_data(tc)
                if tc_data and (
                    tc_data.year < ano_sel
                    or (tc_data.year == ano_sel and tc_data.month <= mes_sel)
                ):
                    if tc.tipo == "Saída":
                        saldo_fatura += tc.valor
                    elif tc.tipo == "Entrada":
                        saldo_fatura = max(0.0, saldo_fatura - tc.valor)

            self.txt_fatura_total.value = f"R$ {saldo_fatura:.2f}"

            novas_sec_cartao = []
            if compras_mes_atual > 0 or pagamentos_mes_atual > 0:
                novas_sec_cartao = [
                    fch.PieChartSection(
                        value=compras_mes_atual if compras_mes_atual > 0 else 0.001,
                        title=f"Gastos\nR$ {compras_mes_atual:.2f}",
                        color=ft.Colors.RED_400,
                        radius=60,
                        title_style=ft.TextStyle(
                            size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                        ),
                    ),
                    fch.PieChartSection(
                        value=pagamentos_mes_atual
                        if pagamentos_mes_atual > 0
                        else 0.001,
                        title=f"Abatimento\nR$ {pagamentos_mes_atual:.2f}",
                        color=ft.Colors.GREEN_400,
                        radius=60,
                        title_style=ft.TextStyle(
                            size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                        ),
                    ),
                ]
            self.chart_cartao.sections = novas_sec_cartao

        except Exception as ex:
            print(f"Erro ao carregar dados: {ex}")

        self.page_ref.update()

    def deletar_transacao_acao(self, transacao_id):
        if remover_transacao(transacao_id):
            mostrar_mensagem(self.page_ref, "Lançamento removido!")
            self.carregar_dados()

    def adicionar_transacao(self, e):
        if not self.perfil_ativo_id[0]:
            mostrar_mensagem(self.page_ref, "Selecione um perfil primeiro!")
            return

        if (
            not self.txt_data.value
            or not self.txt_descricao.value
            or not self.txt_valor.value
        ):
            mostrar_mensagem(self.page_ref, "Preencha todos os campos obrigatórios!")
            return

        val_mes = self.dropdown_filtro_mes.value
        mes_filtro = (
            int(val_mes)
            if str(val_mes).isdigit()
            else MAPA_MESES.get(str(val_mes), date.today().month)
        )
        ano_filtro = int(self.dropdown_filtro_ano.value)
        dia_str = self.txt_data.value.strip()

        if not dia_str.isdigit():
            mostrar_mensagem(
                self.page_ref,
                "❌ Erro: Digite apenas o número do dia (ex: 09 ou 15).",
            )
            self.txt_data.focus()
            return

        try:
            dia_int = int(dia_str)
            data_dt = date(ano_filtro, mes_filtro, dia_int)
        except ValueError:
            mostrar_mensagem(
                self.page_ref,
                f"❌ Erro: O dia '{dia_str}' é inválido para o mês selecionado!",
            )
            self.txt_data.focus()
            return

        try:
            valor_float = float(self.txt_valor.value.replace(",", "."))
        except ValueError:
            mostrar_mensagem(self.page_ref, "❌ Erro: Valor inválido!")
            self.txt_valor.focus()
            return

        try:
            salvar_transacao(
                descricao=self.txt_descricao.value.strip(),
                valor=valor_float,
                tipo=self.dropdown_tipo.value,
                forma_pagamento=self.dropdown_pagamento.value,
                data_dt=data_dt,
                perfil_id=self.perfil_ativo_id[0],
            )

            self.txt_descricao.value = ""
            self.txt_valor.value = ""
            self.txt_data.value = (
                f"{date.today().day:02d}"
                if date.today().month == mes_filtro
                else "01"
            )
            self.carregar_dados()
            mostrar_mensagem(self.page_ref, "✅ Lançamento adicionado com sucesso!")
        except Exception as ex:
            print(f"Erro ao adicionar transação: {ex}")

    def ao_filtrar_data(self, e=None):
        try:
            val_mes = self.dropdown_filtro_mes.value
            mes_sel = (
                int(val_mes)
                if str(val_mes).isdigit()
                else MAPA_MESES.get(str(val_mes), date.today().month)
            )
            ano_sel = int(self.dropdown_filtro_ano.value)
            hoje = date.today()

            if hoje.month == mes_sel and hoje.year == ano_sel:
                self.txt_data.value = f"{hoje.day:02d}"
            else:
                self.txt_data.value = "01"
        except Exception:
            pass

        self.carregar_dados()

    def ao_mudar_perfil_header(self, e):
        if e.control.value:
            self.perfil_ativo_id[0] = int(e.control.value)
            self.carregar_dados()

    def _obter_estilo_aba(self, ativo: bool):
        if ativo:
            return ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE,
                side=ft.BorderSide(1, ft.Colors.BLUE_600),
            )
        return ft.ButtonStyle(
            bgcolor=ft.Colors.TRANSPARENT,
            color=ft.Colors.WHITE,
            side=ft.BorderSide(1, ft.Colors.WHITE_24),
        )

    def mudar_aba(self, aba):
        self.aba_dashboard.visible = aba == "dashboard"
        self.aba_geral.visible = aba == "geral"
        self.aba_cartao_content.visible = aba == "cartao"

        self.btn_tab_dashboard.style = self._obter_estilo_aba(aba == "dashboard")
        self.btn_tab_geral.style = self._obter_estilo_aba(aba == "geral")
        self.btn_tab_cartao.style = self._obter_estilo_aba(aba == "cartao")

        self.carregar_dados()