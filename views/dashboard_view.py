from datetime import date, datetime
import flet as ft
import flet_charts as fch

from database.crud import (
    MAPA_MESES,
    MESES,
    buscar_cartoes_do_perfil,
    buscar_todos_perfis,
    buscar_transacoes_do_perfil,
    calcular_limites_cartao,
    eh_credito,
    remover_transacao,
    salvar_transacao,
)
from utils.date_utils import extrair_data
from utils.ui_helpers import mostrar_mensagem

from views.dialogs.gestao_cartoes_dialog import GestaoCartoesDialog
from views.dialogs.editar_transacao_dialog import EditarTransacaoDialog


def formatar_moeda(valor: float) -> str:
    """Helper para formatar valores no padrão brasileiro (R$ X.XXX,XX)."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def obter_mes_ano_fatura(data_transacao: date, dia_fechamento: int):
    """
    Retorna a tupla (mes, ano) da fatura em que a transação deve ser cobrada.
    Se a data da transação for igual ou posterior ao dia de fechamento,
    ela vai para o mês seguinte.
    """
    if not dia_fechamento or dia_fechamento <= 0:
        return data_transacao.month, data_transacao.year

    if data_transacao.day >= dia_fechamento:
        mes = data_transacao.month + 1
        ano = data_transacao.year
        if mes > 12:
            mes = 1
            ano += 1
        return mes, ano

    return data_transacao.month, data_transacao.year


def adicionar_meses(data_origem: date, meses_para_adicionar: int) -> date:
    """Avança N meses a partir de uma data mantendo um dia válido."""
    ano = data_origem.year + (data_origem.month + meses_para_adicionar - 1) // 12
    mes = (data_origem.month + meses_para_adicionar - 1) % 12 + 1
    dia = min(
        data_origem.day,
        [
            31,
            29 if ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ][mes - 1],
    )
    return date(ano, mes, dia)


class DashboardView(ft.Column):
    def __init__(self, page: ft.Page, perfil_ativo_id, on_trocar_perfil):
        super().__init__(expand=True, visible=False)
        self.page_ref = page
        self.perfil_ativo_id = perfil_ativo_id
        self.on_trocar_perfil_cb = on_trocar_perfil

        # --- INSTANCIAÇÃO DOS DIÁLOGOS MODULARIZADOS ---
        self.dialog_gestao_cartoes = GestaoCartoesDialog(
            page_ref=self.page_ref,
            perfil_ativo_id=self.perfil_ativo_id,
            on_atualizar_dados_dashboard=self.carregar_dados,
        )

        self.dialog_editar = EditarTransacaoDialog(
            page_ref=self.page_ref,
            perfil_ativo_id=self.perfil_ativo_id,
            on_sucesso=self.carregar_dados,
        )

        # Adiciona diálogos no overlay da página
        self.page_ref.overlay.extend(
            [self.dialog_gestao_cartoes, self.dialog_editar]
        )

        # --- HELPERS DE CRIAÇÃO DE CONTROLES ---
        def make_tf(
            label,
            value="",
            width=None,
            expand=False,
            hint="",
            kb=None,
            on_sub=None,
        ):
            return ft.TextField(
                label=label,
                value=value,
                width=width,
                expand=expand,
                hint_text=hint,
                keyboard_type=kb,
                on_submit=on_sub,
                content_padding=ft.Padding(
                    left=12, right=12, top=12, bottom=12
                ),
            )

        def make_dd(
            label,
            options,
            value=None,
            width=None,
            expand=False,
            on_change=None,
        ):
            opts = []
            for opt in options:
                if isinstance(opt, tuple):
                    k, v = opt
                    opts.append(ft.dropdown.Option(str(k), text=str(v)))
                else:
                    opts.append(ft.dropdown.Option(str(opt)))

            return ft.Dropdown(
                label=label,
                width=width,
                expand=expand,
                value=value,
                options=opts,
                on_select=on_change,
                content_padding=ft.Padding(
                    left=12, right=12, top=12, bottom=12
                ),
                menu_height=200,
            )

        # --- COMPONENTES PRINCIPAIS ---
        self.txt_data = make_tf(
            "Dia", value=f"{date.today().day:02d}", width=80, hint="DD"
        )
        self.txt_descricao = make_tf(
            "Descrição", expand=True, on_sub=self.adicionar_transacao
        )
        self.txt_valor = make_tf(
            "Valor Total (R$)",
            width=140,
            kb=ft.KeyboardType.NUMBER,
            on_sub=self.adicionar_transacao,
        )

        self.dropdown_filtro_mes = make_dd(
            "Mês da Fatura",
            MESES,
            value=str(datetime.now().month),
            width=160,
            on_change=self.ao_filtrar_data,
        )
        self.dropdown_filtro_ano = make_dd(
            "Ano",
            [str(y) for y in range(2024, 2028)],
            value=str(datetime.now().year),
            width=110,
            on_change=self.ao_filtrar_data,
        )
        self.dropdown_perfis_header = make_dd(
            "Perfil Ativo", [], width=170, on_change=self.ao_mudar_perfil_header
        )

        self.dropdown_tipo = make_dd(
            "Tipo", ["Entrada", "Saída"], value="Saída", width=130
        )
        self.dropdown_pagamento = make_dd(
            "Pagamento",
            ["Dinheiro", "PIX", "Crédito", "Débito"],
            value="PIX",
            width=145,
            on_change=self.ao_mudar_forma_pagamento,
        )
        self.dropdown_cartao = make_dd("Cartão", [], width=150)
        self.dropdown_cartao.disabled = True

        # CONTROLES DE PARCELAMENTO
        self.chk_parcelado = ft.Checkbox(
            label="Parcelado?",
            value=False,
            disabled=True,
            on_change=self.ao_mudar_parcelado,
        )
        self.txt_num_parcelas = make_tf(
            "Nº Parc.",
            value="2",
            width=90,
            kb=ft.KeyboardType.NUMBER,
            hint="Ex: 4",
            on_sub=self.adicionar_transacao,
        )
        self.txt_num_parcelas.visible = False

        self.btn_salvar = ft.FilledButton(
            "Adicionar",
            icon=ft.Icons.ADD,
            height=48,
            style=ft.ButtonStyle(
                padding=ft.Padding(left=12, right=12, top=12, bottom=12),
            ),
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.adicionar_transacao,
        )

        # --- FORMULÁRIO DE NOVO LANÇAMENTO ---
        self.row_formulario_lancamento = ft.Row(
            [
                self.txt_data,
                self.txt_descricao,
                self.txt_valor,
                self.dropdown_tipo,
                self.dropdown_pagamento,
                self.dropdown_cartao,
                self.chk_parcelado,
                self.txt_num_parcelas,
                self.btn_salvar,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False,
        )

        self.txt_kpi_entradas = self._txt_kpi(ft.Colors.GREEN_400)
        self.txt_kpi_saidas = self._txt_kpi(ft.Colors.RED_400)
        self.txt_kpi_saldo = self._txt_kpi(ft.Colors.BLUE_400)
        self.txt_fatura_total = self._txt_kpi(ft.Colors.AMBER_400)

        self.chart_geral = fch.PieChart(
            sections=[], sections_space=2, center_space_radius=45, expand=True
        )

        self.chart_cartao = fch.PieChart(
            sections=[], sections_space=2, center_space_radius=25, expand=True
        )

        # Container dinâmico do bloco do Cartão de Crédito
        self.container_cartao_dashboard = ft.Container(
            padding=15,
            height=300,
            border=ft.Border.all(1, ft.Colors.WHITE_24),
            border_radius=10,
            expand=True,
        )

        self.tabela_geral = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(col))
                for col in [
                    "Data",
                    "Descrição",
                    "Tipo",
                    "Pagamento",
                    "Valor",
                    "Ações",
                ]
            ],
            rows=[],
            expand=True,
        )
        self.tabela_cartao = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(col))
                for col in [
                    "Data",
                    "Descrição",
                    "Tipo",
                    "Cartão",
                    "Valor",
                    "Ações",
                ]
            ],
            rows=[],
            expand=True,
        )

        self._construir_aba_dashboard()
        self.aba_geral = self._criar_aba_tabela(
            "Histórico de Lançamentos", self.tabela_geral
        )
        self.aba_cartao_content = self._criar_aba_cartao()

        # Botões de Navegação das Abas
        self.btn_tab_dashboard = ft.OutlinedButton(
            "Dashboard",
            icon=ft.Icons.ANALYTICS_OUTLINED,
            style=self._obter_estilo_aba(True),
            on_click=lambda e: self.mudar_aba("dashboard"),
        )
        self.btn_tab_geral = ft.OutlinedButton(
            "Lançamentos Gerais",
            icon=ft.Icons.TABLE_ROWS_OUTLINED,
            style=self._obter_estilo_aba(False),
            on_click=lambda e: self.mudar_aba("geral"),
        )
        self.btn_tab_cartao = ft.OutlinedButton(
            "Cartão de Crédito",
            icon=ft.Icons.CREDIT_CARD,
            style=self._obter_estilo_aba(False),
            on_click=lambda e: self.mudar_aba("cartao"),
        )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        "Painel Financeiro", size=24, weight=ft.FontWeight.BOLD
                    ),
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
                    self.btn_tab_dashboard,
                    self.btn_tab_geral,
                    self.btn_tab_cartao,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(),
            self.row_formulario_lancamento,
            ft.Stack(
                controls=[
                    self.aba_dashboard,
                    self.aba_geral,
                    self.aba_cartao_content,
                ],
                expand=True,
            ),
        ]

    def _txt_kpi(self, color):
        return ft.Text(
            "R$ 0,00", size=20, weight=ft.FontWeight.BOLD, color=color
        )

    def _criar_card_kpi(self, titulo, controle_texto, icone, cor_icone):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icone, size=30, color=cor_icone),
                    ft.Column(
                        [
                            ft.Text(
                                titulo,
                                size=12,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.GREY_300,
                            ),
                            controle_texto,
                        ],
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=15,
            border=ft.Border.all(1, ft.Colors.WHITE_24),
            border_radius=10,
            expand=True,
        )

    def _criar_aba_tabela(self, titulo, tabela):
        return ft.Container(
            content=ft.Column(
                [ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD), tabela],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
            visible=False,
            expand=True,
        )

    def _criar_aba_cartao(self):
        header_cartao = ft.Row(
            [
                ft.Text(
                    "Histórico de Faturas e Cartões",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.TextButton(
                    "Gerenciar Cartões",
                    icon=ft.Icons.SETTINGS,
                    icon_color=ft.Colors.BLUE_400,
                    on_click=lambda e: self.abrir_gestao_cartoes(),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        return ft.Container(
            content=ft.Column(
                [header_cartao, self.tabela_cartao],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
            visible=False,
            expand=True,
        )

    def _construir_aba_dashboard(self):
        cards_kpi = ft.Row(
            [
                self._criar_card_kpi(
                    "Entradas no Mês",
                    self.txt_kpi_entradas,
                    ft.Icons.ARROW_UPWARD,
                    ft.Colors.GREEN_400,
                ),
                self._criar_card_kpi(
                    "Saídas no Mês",
                    self.txt_kpi_saidas,
                    ft.Icons.ARROW_DOWNWARD,
                    ft.Colors.RED_400,
                ),
                self._criar_card_kpi(
                    "Saldo Líquido",
                    self.txt_kpi_saldo,
                    ft.Icons.ACCOUNT_BALANCE_WALLET,
                    ft.Colors.BLUE_400,
                ),
                self._criar_card_kpi(
                    "Fatura de Crédito",
                    self.txt_fatura_total,
                    ft.Icons.CREDIT_CARD,
                    ft.Colors.AMBER_400,
                ),
            ],
            spacing=15,
        )

        def make_chart_box(title, chart):
            content = [
                ft.Text(title, size=15, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=chart, expand=True, alignment=ft.Alignment(0, 0)
                ),
            ]
            return ft.Container(
                content=ft.Column(
                    content,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=15,
                height=300,
                border=ft.Border.all(1, ft.Colors.WHITE_24),
                border_radius=10,
                expand=True,
            )

        graficos_row = ft.Row(
            [
                make_chart_box("Entradas x Saídas", self.chart_geral),
                self.container_cartao_dashboard,
            ],
            spacing=15,
            expand=True,
        )

        self.aba_dashboard = ft.Container(
            content=ft.Column(
                [
                    cards_kpi,
                    ft.Container(height=15),
                    graficos_row,
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
            visible=True,
            expand=True,
        )

    # --- GERENCIAMENTO DE DIÁLOGOS ---
    def abrir_gestao_cartoes(self):
        if not self.perfil_ativo_id[0]:
            mostrar_mensagem(self.page_ref, "❌ Selecione um perfil primeiro!")
            return
        self.dialog_gestao_cartoes.abrir()

    def abrir_dialog_edicao(self, transacao):
        self.dialog_editar.abrir_para_edicao(transacao)

    # --- MÉTODOS AUXILIARES E EVENTOS ---
    def ao_mudar_forma_pagamento(self, e=None):
        is_credito = eh_credito(self.dropdown_pagamento.value)
        self.dropdown_cartao.disabled = not is_credito
        self.chk_parcelado.disabled = not is_credito

        if not is_credito:
            self.dropdown_cartao.value = None
            self.chk_parcelado.value = False
            self.txt_num_parcelas.visible = False

        self.dropdown_cartao.update()
        self.chk_parcelado.update()
        self.txt_num_parcelas.update()

    def ao_mudar_parcelado(self, e=None):
        self.txt_num_parcelas.visible = self.chk_parcelado.value
        self.txt_num_parcelas.update()

    def carregar_opcoes_cartoes(self):
        if not self.perfil_ativo_id[0]:
            return
        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        self.dropdown_cartao.options = [
            ft.dropdown.Option(key=str(c.id), text=c.nome) for c in cartoes
        ]
        if self.dropdown_cartao.options and not self.dropdown_cartao.value:
            self.dropdown_cartao.value = self.dropdown_cartao.options[0].key

    def _obter_dados_form(self):
        try:
            mes = int(self.dropdown_filtro_mes.value)
            ano = int(self.dropdown_filtro_ano.value)
            dia = int(self.txt_data.value.strip())
            dt = date(ano, mes, dia)

            val_str = (
                str(self.txt_valor.value or "")
                .replace("R$", "")
                .replace(" ", "")
                .replace(",", ".")
                .strip()
            )
            val = float(val_str)

            desc = (
                self.txt_descricao.value.strip()
                if self.txt_descricao.value
                else ""
            )
            if not desc:
                raise ValueError("Descrição vazia")

            cartao_id = (
                int(self.dropdown_cartao.value)
                if (
                    eh_credito(self.dropdown_pagamento.value)
                    and self.dropdown_cartao.value
                )
                else None
            )

            parcelas = 1
            if (
                eh_credito(self.dropdown_pagamento.value)
                and self.chk_parcelado.value
            ):
                parcelas_str = (
                    self.txt_num_parcelas.value.strip()
                    if self.txt_num_parcelas.value
                    else "1"
                )
                parcelas = max(1, int(parcelas_str))

            return dt, val, desc, cartao_id, parcelas
        except Exception:
            return None, None, None, None, 1

    def carregar_perfis_header(self):
        perfis = buscar_todos_perfis()
        self.dropdown_perfis_header.options = [
            ft.dropdown.Option(key=str(p.id), text=p.nome) for p in perfis
        ]
        if self.perfil_ativo_id[0]:
            self.dropdown_perfis_header.value = str(self.perfil_ativo_id[0])

    def _gerar_linhas_tabela(
        self, transacoes, modo_cartao=False, mapa_cartoes=None
    ):
        linhas = []
        mapa_c = mapa_cartoes or {}
        for t in transacoes:
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

            t_data = extrair_data(t)
            data_fmt = t_data.strftime("%d/%m/%Y") if t_data else "-"
            cor_val = (
                ft.Colors.GREEN_400
                if t.tipo == "Entrada"
                else ft.Colors.RED_400
            )

            cells = [
                ft.DataCell(ft.Text(data_fmt)),
                ft.DataCell(ft.Text(t.descricao)),
                ft.DataCell(ft.Text(t.tipo)),
            ]

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
                        ft.Text(formatar_moeda(t.valor), color=cor_val)
                    ),
                    ft.DataCell(ft.Row([btn_edit, btn_del], spacing=0)),
                ]
            )
            linhas.append(ft.DataRow(cells=cells))
        return linhas

    def carregar_dados(self):
        if not self.perfil_ativo_id[0]:
            self.page_ref.update()
            return

        try:
            self.carregar_opcoes_cartoes()

            cartoes_lista = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
            mapa_cartoes = {c.id: c for c in cartoes_lista}

            val_mes = self.dropdown_filtro_mes.value
            mes_sel = (
                int(val_mes)
                if str(val_mes).isdigit()
                else MAPA_MESES.get(str(val_mes), date.today().month)
            )
            ano_sel = int(self.dropdown_filtro_ano.value or date.today().year)

            transacoes_todas = buscar_transacoes_do_perfil(
                self.perfil_ativo_id[0]
            )

            # --- FILTRAGEM DO MÊS PARA O DASHBOARD GERAL ---
            transacoes_mes = [
                t
                for t in transacoes_todas
                if (dt := extrair_data(t))
                and dt.month == mes_sel
                and dt.year == ano_sel
            ]

            total_entradas = sum(
                t.valor for t in transacoes_mes if t.tipo == "Entrada"
            )
            total_saidas = sum(
                t.valor for t in transacoes_mes if t.tipo == "Saída"
            )

            self.tabela_geral.rows = self._gerar_linhas_tabela(
                transacoes_mes, modo_cartao=False
            )

            saldo_mes = total_entradas - total_saidas
            self.txt_kpi_entradas.value = formatar_moeda(total_entradas)
            self.txt_kpi_saidas.value = formatar_moeda(total_saidas)
            self.txt_kpi_saldo.value = formatar_moeda(saldo_mes)
            self.txt_kpi_saldo.color = (
                ft.Colors.GREEN_400 if saldo_mes >= 0 else ft.Colors.RED_400
            )

            tot_geral = total_entradas + total_saidas
            if tot_geral > 0:
                self.chart_geral.sections = [
                    fch.PieChartSection(
                        value=total_entradas or 0.001,
                        title=f"Entradas\n{(total_entradas/tot_geral)*100:.1f}%",
                        color=ft.Colors.BLUE_400,
                        radius=60,
                        title_style=ft.TextStyle(
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                    fch.PieChartSection(
                        value=total_saidas or 0.001,
                        title=f"Saídas\n{(total_saidas/tot_geral)*100:.1f}%",
                        color=ft.Colors.RED_400,
                        radius=60,
                        title_style=ft.TextStyle(
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                ]
            else:
                self.chart_geral.sections = []

            # --- TRANSAÇÕES DO CARTÃO NO MÊS SELECIONADO ---
            tc_mes = []
            for t in transacoes_todas:
                if (
                    eh_credito(t.forma_pagamento)
                    or getattr(t, "cartao_id", None) is not None
                ):
                    t_dt = extrair_data(t)
                    if not t_dt:
                        continue

                    dia_fechamento = None
                    if hasattr(t, "cartao") and t.cartao:
                        dia_fechamento = t.cartao.dia_fechamento
                    elif getattr(t, "cartao_id", None) in mapa_cartoes:
                        dia_fechamento = mapa_cartoes[t.cartao_id].dia_fechamento

                    mes_fatura, ano_fatura = obter_mes_ano_fatura(
                        t_dt, dia_fechamento
                    )

                    if mes_fatura == mes_sel and ano_fatura == ano_sel:
                        tc_mes.append(t)

            compras_mes_atual = sum(
                tc.valor for tc in tc_mes if tc.tipo == "Saída"
            )
            pagamentos_mes_atual = sum(
                tc.valor for tc in tc_mes if tc.tipo == "Entrada"
            )

            self.tabela_cartao.rows = self._gerar_linhas_tabela(
                tc_mes, modo_cartao=True, mapa_cartoes=mapa_cartoes
            )

            fatura_mes_atual = max(
                0.0, compras_mes_atual - pagamentos_mes_atual
            )
            self.txt_fatura_total.value = formatar_moeda(fatura_mes_atual)

            # --- CÁLCULO E EXIBIÇÃO DO LIMITE DO CARTÃO (DÍVIDA REAL ATUAL) ---
            limite_total_perfil = sum(c.limite or 0.0 for c in cartoes_lista)
            
            # Limite comprometido = (Todas Saídas do Cartão no Perfil) - (Todas Entradas do Cartão no Perfil)
            todas_saidas_cartao = sum(
                t.valor
                for t in transacoes_todas
                if (eh_credito(t.forma_pagamento) or getattr(t, "cartao_id", None))
                and t.tipo == "Saída"
            )
            todas_entradas_cartao = sum(
                t.valor
                for t in transacoes_todas
                if (eh_credito(t.forma_pagamento) or getattr(t, "cartao_id", None))
                and t.tipo == "Entrada"
            )

            limite_comprometido_perfil = max(
                0.0, todas_saidas_cartao - todas_entradas_cartao
            )
            limite_disponivel_perfil = max(
                0.0, limite_total_perfil - limite_comprometido_perfil
            )

            perc_comprometido = (
                (limite_comprometido_perfil / limite_total_perfil)
                if limite_total_perfil > 0
                else 0.0
            )
            cor_barra_limite = (
                ft.Colors.GREEN_400
                if perc_comprometido < 0.7
                else (
                    ft.Colors.AMBER_400
                    if perc_comprometido < 0.9
                    else ft.Colors.RED_400
                )
            )

            # --- MONTAGEM DO GRÁFICO DO MÊS SELECIONADO ---
            if compras_mes_atual > 0 or pagamentos_mes_atual > 0:
                self.chart_cartao.sections = [
                    fch.PieChartSection(
                        value=compras_mes_atual if compras_mes_atual > 0 else 0.001,
                        title=f"Gastos\n{formatar_moeda(compras_mes_atual)}",
                        color=ft.Colors.RED_400,
                        radius=28,
                        title_style=ft.TextStyle(
                            size=9,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                    fch.PieChartSection(
                        value=pagamentos_mes_atual if pagamentos_mes_atual > 0 else 0.001,
                        title=f"Abatimento\n{formatar_moeda(pagamentos_mes_atual)}",
                        color=ft.Colors.GREEN_400,
                        radius=28,
                        title_style=ft.TextStyle(
                            size=9,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                ]
            else:
                self.chart_cartao.sections = []

            # --- CONSTRUÇÃO VISUAL DO CARD ---
            self.container_cartao_dashboard.content = ft.Column(
                [
                    ft.Text(
                        "Fatura e Limite do Cartão",
                        size=15,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=self.chart_cartao,
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Divider(height=1, color=ft.Colors.WHITE_12),
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        "Limite Geral do Perfil",
                                        size=12,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.GREY_300,
                                    ),
                                    ft.Text(
                                        f"{perc_comprometido*100:.1f}% usado",
                                        size=11,
                                        color=cor_barra_limite,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.ProgressBar(
                                value=min(1.0, perc_comprometido),
                                color=cor_barra_limite,
                                bgcolor=ft.Colors.WHITE_10,
                                height=8,
                            ),
                            ft.Row(
                                [
                                    ft.Text(
                                        f"Disp: {formatar_moeda(limite_disponivel_perfil)}",
                                        color=ft.Colors.GREEN_400,
                                        size=11,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(
                                        f"Usado: {formatar_moeda(limite_comprometido_perfil)}",
                                        color=ft.Colors.RED_400,
                                        size=11,
                                    ),
                                    ft.Text(
                                        f"Total: {formatar_moeda(limite_total_perfil)}",
                                        color=ft.Colors.GREY_400,
                                        size=11,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=6,
            )

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

        dt, val_total, desc, cartao_id, parcelas = self._obter_dados_form()
        if not dt or val_total is None or not desc:
            mostrar_mensagem(
                self.page_ref,
                "❌ Erro: Preencha todos os campos corretamente!",
            )
            return

        try:
            valor_parcela = round(val_total / parcelas, 2)

            for i in range(parcelas):
                dt_parcela = adicionar_meses(dt, i)
                desc_parcela = (
                    f"{desc} ({i+1}/{parcelas})" if parcelas > 1 else desc
                )

                salvar_transacao(
                    descricao=desc_parcela,
                    valor=valor_parcela,
                    tipo=self.dropdown_tipo.value,
                    forma_pagamento=self.dropdown_pagamento.value,
                    data_dt=dt_parcela,
                    perfil_id=self.perfil_ativo_id[0],
                    cartao_id=cartao_id,
                )

            self.txt_descricao.value = ""
            self.txt_valor.value = ""
            self.chk_parcelado.value = False
            self.txt_num_parcelas.visible = False
            self.txt_num_parcelas.value = "2"

            self.ao_filtrar_data()
            msg_sucesso = (
                f"✅ Lançamento em {parcelas}x salvo com sucesso!"
                if parcelas > 1
                else "✅ Lançamento adicionado com sucesso!"
            )
            mostrar_mensagem(self.page_ref, msg_sucesso)

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
            self.txt_data.value = (
                f"{hoje.day:02d}"
                if hoje.month == mes_sel and hoje.year == ano_sel
                else "01"
            )
        except Exception:
            pass
        self.carregar_dados()

    def ao_mudar_perfil_header(self, e):
        if e.control.value:
            self.perfil_ativo_id[0] = int(e.control.value)
            self.carregar_dados()

    def _obter_estilo_aba(self, ativo: bool):
        bg = ft.Colors.BLUE_600 if ativo else ft.Colors.TRANSPARENT
        side = ft.Colors.BLUE_600 if ativo else ft.Colors.WHITE_24
        return ft.ButtonStyle(
            bgcolor=bg, color=ft.Colors.WHITE, side=ft.BorderSide(1, side)
        )

    def mudar_aba(self, aba):
        self.aba_dashboard.visible = aba == "dashboard"
        self.aba_geral.visible = aba == "geral"
        self.aba_cartao_content.visible = aba == "cartao"

        self.row_formulario_lancamento.visible = aba == "geral"

        self.btn_tab_dashboard.style = self._obter_estilo_aba(aba == "dashboard")
        self.btn_tab_geral.style = self._obter_estilo_aba(aba == "geral")
        self.btn_tab_cartao.style = self._obter_estilo_aba(aba == "cartao")

        self.carregar_dados()