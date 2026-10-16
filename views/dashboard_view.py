from datetime import date, datetime
import flet as ft
import flet_charts as fch

from database.crud import (
    MAPA_MESES,
    MESES,
    buscar_todos_perfis,
    eh_credito,
    remover_transacao,
    salvar_transacao,
    obter_ou_criar_fatura_mensal,
    atualizar_status_fatura,
    calcular_limites_cartao,
)
from services.fatura_service import projetar_faturas_futuras, obter_mes_ano_fatura
from controllers.dashboard_controller import DashboardController
from views.dialogs.gestao_cartoes_dialog import GestaoCartoesDialog
from views.dialogs.editar_transacao_dialog import EditarTransacaoDialog

# Componentes modularizados
from views.components.kpi_cards import criar_linha_kpis
from views.components.cartao_card import criar_card_cartao
from views.components.tabelas_transacoes import gerar_linhas_tabela


def extrair_data(t):
    return getattr(t, "data", None) or getattr(t, "data_dt", None)


def formatar_moeda(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mostrar_mensagem(page: ft.Page, mensagem: str):
    page.snack_bar = ft.SnackBar(ft.Text(mensagem))
    page.snack_bar.open = True
    page.update()


class DashboardView(ft.Column):
    def __init__(self, page: ft.Page, perfil_ativo_id, on_trocar_perfil):
        super().__init__(expand=True, visible=False)
        self.page_ref = page
        self.perfil_ativo_id = perfil_ativo_id
        self.on_trocar_perfil_cb = on_trocar_perfil

        # Instanciação do Controller de Negócios
        self.controller = DashboardController(perfil_ativo_id)

        # Diálogos
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
        self.page_ref.overlay.extend([self.dialog_gestao_cartoes, self.dialog_editar])

        # Construção de controles de formulário e filtros
        self._construir_controles_ui()
        self._construir_layout_principal()

    def _construir_controles_ui(self):
        def make_tf(label, value="", width=None, expand=False, hint="", kb=None, on_sub=None):
            return ft.TextField(
                label=label, value=value, width=width, expand=expand, hint_text=hint,
                keyboard_type=kb, on_submit=on_sub,
                content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
            )

        def make_dd(label, options, value=None, width=None, expand=False, on_select=None):
            opts = [ft.dropdown.Option(str(o[0]), text=str(o[1])) if isinstance(o, tuple) else ft.dropdown.Option(str(o)) for o in options]
            return ft.Dropdown(
                label=label, width=width, expand=expand, value=value, options=opts,
                on_select=on_select, content_padding=ft.Padding(left=12, right=12, top=12, bottom=12), menu_height=200,
            )

        self.txt_data = make_tf("Dia", value=f"{date.today().day:02d}", width=80, hint="DD")
        self.txt_descricao = make_tf("Descrição", expand=True, on_sub=self.adicionar_transacao)
        self.txt_valor = make_tf("Valor Total (R$)", width=140, kb=ft.KeyboardType.NUMBER, on_sub=self.adicionar_transacao)

        self.dropdown_filtro_mes = make_dd("Mês da Fatura", MESES, value=str(datetime.now().month), width=160, on_select=self.ao_filtrar_data)
        self.dropdown_filtro_ano = make_dd("Ano", [str(y) for y in range(2024, 2028)], value=str(datetime.now().year), width=110, on_select=self.ao_filtrar_data)
        self.dropdown_perfis_header = make_dd("Perfil Ativo", [], width=170, on_select=self.ao_mudar_perfil_header)

        self.dropdown_tipo = make_dd("Tipo", ["Entrada", "Saída"], value="Saída", width=130)
        self.dropdown_pagamento = make_dd("Pagamento", ["Dinheiro", "PIX", "Crédito", "Débito"], value="PIX", width=145, on_select=self.ao_mudar_forma_pagamento)
        self.dropdown_cartao = make_dd("Cartão", [], width=150)
        self.dropdown_cartao.disabled = True

        self.campo_busca = ft.TextField(
            label="Pesquisar descrição...", text_size=12, height=40, expand=True,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            on_change=lambda e: self.carregar_dados(),
        )
        self.dropdown_filtro_forma = ft.Dropdown(
            label="Forma de Pagto.", text_size=12, height=40, width=160,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            options=[ft.dropdown.Option(o) for o in ["Todas", "Crédito", "Débito", "PIX", "Dinheiro"]],
            value="Todas", on_select=lambda e: self.carregar_dados(),
        )

        self.chk_parcelado = ft.Checkbox(label="Parcelado?", value=False, disabled=True, on_change=self.ao_mudar_parcelado)
        self.txt_num_parcelas = make_tf("Nº Parc.", value="2", width=90, kb=ft.KeyboardType.NUMBER, hint="Ex: 4", on_sub=self.adicionar_transacao)
        self.txt_num_parcelas.visible = False

        self.btn_salvar = ft.FilledButton("Adicionar", icon=ft.Icons.ADD, height=48, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=self.adicionar_transacao)

        self.row_formulario_lancamento = ft.Row(
            [self.txt_data, self.txt_descricao, self.txt_valor, self.dropdown_tipo, self.dropdown_pagamento, self.dropdown_cartao, self.chk_parcelado, self.txt_num_parcelas, self.btn_salvar],
            spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, visible=False,
        )

        self.txt_kpi_entradas = self._txt_kpi(ft.Colors.GREEN_400)
        self.txt_kpi_saidas = self._txt_kpi(ft.Colors.RED_400)
        self.txt_kpi_saldo = self._txt_kpi(ft.Colors.BLUE_400)
        self.txt_fatura_total = self._txt_kpi(ft.Colors.AMBER_400)

        self.chart_geral = fch.PieChart(sections=[], sections_space=2, center_space_radius=40)
        self.coluna_cartoes_dashboard = ft.Column(spacing=15, width=340, scroll=ft.ScrollMode.AUTO)

        self.tabela_geral = ft.DataTable(columns=[ft.DataColumn(ft.Text(c)) for c in ["Data", "Descrição", "Tipo", "Pagamento", "Valor", "Ações"]], rows=[], expand=True)
        self.tabela_cartao = ft.DataTable(columns=[ft.DataColumn(ft.Text(c)) for c in ["Data", "Descrição", "Tipo", "Cartão", "Valor", "Ações"]], rows=[], expand=True)

        self.barra_filtros_ui = ft.Row([self.campo_busca, self.dropdown_filtro_forma], spacing=10)
        self.aba_geral = self._criar_aba_tabela("Histórico de Lançamentos", self.tabela_geral, com_filtros=True)
        self.aba_cartao_content = self._criar_aba_cartao()

        self.btn_tab_dashboard = ft.OutlinedButton("Dashboard", icon=ft.Icons.ANALYTICS_OUTLINED, style=self._obter_estilo_aba(True), on_click=lambda e: self.mudar_aba("dashboard"))
        self.btn_tab_geral = ft.OutlinedButton("Lançamentos Gerais", icon=ft.Icons.TABLE_ROWS_OUTLINED, style=self._obter_estilo_aba(False), on_click=lambda e: self.mudar_aba("geral"))
        self.btn_tab_cartao = ft.OutlinedButton("Cartão de Crédito", icon=ft.Icons.CREDIT_CARD, style=self._obter_estilo_aba(False), on_click=lambda e: self.mudar_aba("cartao"))

    def _txt_kpi(self, color):
        return ft.Text("R$ 0,00", size=20, weight=ft.FontWeight.BOLD, color=color)

    def _criar_aba_tabela(self, titulo, tabela, com_filtros=False):
        controles = [ft.Row([ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)]
        if com_filtros:
            controles.append(self.barra_filtros_ui)
        controles.append(tabela)
        return ft.Container(content=ft.Column(controles, expand=True, scroll=ft.ScrollMode.AUTO, spacing=10), padding=10, visible=False, expand=True)

    def _criar_aba_cartao(self):
        header_cartao = ft.Row([
            ft.Text("Histórico de Faturas e Cartões", size=18, weight=ft.FontWeight.BOLD),
            ft.TextButton("Gerenciar Cartões", icon=ft.Icons.SETTINGS, icon_color=ft.Colors.BLUE_400, on_click=lambda e: self.abrir_gestao_cartoes()),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        return ft.Container(content=ft.Column([header_cartao, self.barra_filtros_ui, self.tabela_cartao], expand=True, scroll=ft.ScrollMode.AUTO, spacing=10), padding=10, visible=False, expand=True)

    def _construir_layout_principal(self):
        cards_kpi = criar_linha_kpis(self.txt_kpi_entradas, self.txt_kpi_saidas, self.txt_kpi_saldo, self.txt_fatura_total)

        def make_chart_box(title, chart):
            return ft.Container(
                content=ft.Column([
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD),
                    ft.Container(content=chart, width=300, height=220, alignment=ft.Alignment(0, 0)),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=15, height=290, border=ft.Border.all(1, ft.Colors.WHITE_24), border_radius=10, expand=True,
            )

        # Forçamos a coluna de cartões a ter exatamente a mesma altura (290) e scroll interno
        container_cartoes_lateral = ft.Container(
            content=self.coluna_cartoes_dashboard,
            height=290,
            width=330,
            padding=0,
        )

        graficos_row = ft.Row([
            make_chart_box("Entradas x Saídas", self.chart_geral),
            container_cartoes_lateral,
        ], spacing=15, expand=False, vertical_alignment=ft.CrossAxisAlignment.START)

        self.aba_dashboard = ft.Container(
            content=ft.Column([cards_kpi, ft.Container(height=15), graficos_row], expand=True, scroll=ft.ScrollMode.AUTO),
            padding=10, visible=True, expand=True,
        )

        header = ft.Container(
            content=ft.Row([
                ft.Text("Painel Financeiro", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("Período:", weight=ft.FontWeight.BOLD),
                    self.dropdown_filtro_mes, self.dropdown_filtro_ano,
                    ft.VerticalDivider(), self.dropdown_perfis_header,
                    ft.TextButton("Trocar Perfil", icon=ft.Icons.SWAP_HORIZ, on_click=lambda e: self.on_trocar_perfil_cb()),
                ], alignment=ft.MainAxisAlignment.END, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            margin=10,
        )

        self.controls = [
            header,
            ft.Row([self.btn_tab_dashboard, self.btn_tab_geral, self.btn_tab_cartao], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(),
            self.row_formulario_lancamento,
            ft.Stack(controls=[self.aba_dashboard, self.aba_geral, self.aba_cartao_content], expand=True),
        ]

    # --- MÉTODOS DE AÇÃO E DADOS ---
    def carregar_dados(self):
        """Método coordenador principal: busca os dados e delega a atualização visual."""
        if not self.perfil_ativo_id[0]:
            self.page_ref.update()
            return

        try:
            self.carregar_opcoes_cartoes()
            
            # Parâmetros de filtro atuais
            mes_sel = int(self.dropdown_filtro_mes.value) if str(self.dropdown_filtro_mes.value).isdigit() else MAPA_MESES.get(str(self.dropdown_filtro_mes.value), date.today().month)
            ano_sel = int(self.dropdown_filtro_ano.value or date.today().year)
            texto_busca = (self.campo_busca.value or "").strip().lower()
            forma_sel = self.dropdown_filtro_forma.value

            # Obtém o dicionário de dados já processados pelo Controller
            dados = self.controller.obter_dados_filtrados(mes_sel, ano_sel, texto_busca, forma_sel)
            if not dados:
                return

            # Delega a atualização para métodos menores e especializados
            self._atualizar_kpis(dados)
            self._atualizar_tabelas(dados)
            self._atualizar_grafico_geral(dados)
            self._atualizar_cards_cartoes(dados, mes_sel, ano_sel)

            self.page_ref.update()

        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao carregar dados: {ex}")

    def _atualizar_kpis(self, dados):
        """Atualiza os valores e cores dos KPIs superiores."""
        total_entradas = dados["total_entradas"]
        total_saidas = dados["total_saidas"]
        saldo_mes = dados["saldo_mes"]

        self.txt_kpi_entradas.value = formatar_moeda(total_entradas)
        self.txt_kpi_saidas.value = formatar_moeda(total_saidas)
        self.txt_kpi_saldo.value = formatar_moeda(saldo_mes)
        self.txt_kpi_saldo.color = ft.Colors.GREEN_400 if saldo_mes >= 0 else ft.Colors.RED_400
        self.txt_fatura_total.value = formatar_moeda(dados["fatura_mes_total"])

    def _atualizar_tabelas(self, dados):
        """Popula as linhas das tabelas geral e de cartões."""
        self.tabela_geral.rows = gerar_linhas_tabela(
            dados["transacoes_mes"], self.abrir_dialog_edicao, self.deletar_transacao_acao, extrair_data, formatar_moeda, modo_cartao=False
        )
        self.tabela_cartao.rows = gerar_linhas_tabela(
            dados["tc_mes"], self.abrir_dialog_edicao, self.deletar_transacao_acao, extrair_data, formatar_moeda, modo_cartao=True, mapa_cartoes=dados["mapa_cartoes"]
        )

    def _atualizar_grafico_geral(self, dados):
        """Atualiza o gráfico de pizza principal (Entradas x Saídas)."""
        tot_geral = dados["total_entradas"] + dados["total_saidas"]
        if tot_geral > 0:
            self.chart_geral.sections = [
                fch.PieChartSection(value=dados["total_entradas"] or 0.001, title=f"Entradas\n{(dados['total_entradas']/tot_geral)*100:.1f}%", color=ft.Colors.BLUE_400, radius=55, title_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)),
                fch.PieChartSection(value=dados["total_saidas"] or 0.001, title=f"Saídas\n{(dados['total_saidas']/tot_geral)*100:.1f}%", color=ft.Colors.RED_400, radius=55, title_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)),
            ]
        else:
            self.chart_geral.sections = [fch.PieChartSection(value=1.0, title="Sem dados", color=ft.Colors.GREY_700, radius=55, title_style=ft.TextStyle(size=11, color=ft.Colors.WHITE))]

    def _atualizar_cards_cartoes(self, dados, mes_sel, ano_sel):
        cards_cartoes_ui = []
        for cartao in dados["cartoes_lista"]:
            card_container = criar_card_cartao(
                page_ref=self.page_ref, cartao=cartao, mes_sel=mes_sel, ano_sel=ano_sel,
                transacoes_todas=dados["transacoes_todas"], mapa_cartoes=dados["mapa_cartoes"],
                on_atualizar_dados=self.carregar_dados, formatar_moeda_func=formatar_moeda,
                mostrar_mensagem_func=mostrar_mensagem, obter_ou_criar_fatura_mensal_func=obter_ou_criar_fatura_mensal,
                atualizar_status_fatura_func=atualizar_status_fatura, calcular_limites_cartao_func=calcular_limites_cartao,
                projetar_faturas_futuras_func=projetar_faturas_futuras, obter_mes_ano_fatura_func=obter_mes_ano_fatura, MESES_LISTA=MESES,
            )
            cards_cartoes_ui.append(card_container)

        if not cards_cartoes_ui:
            cards_cartoes_ui.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.CREDIT_CARD_OFF, size=40, color=ft.Colors.GREY_500),
                        ft.Text("Nenhum cartão cadastrado", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
                        ft.ElevatedButton("Cadastrar Cartão", icon=ft.Icons.ADD, on_click=lambda e: self.abrir_gestao_cartoes()),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=20, border=ft.Border.all(1, ft.Colors.WHITE_12), border_radius=10, width=320, alignment=ft.Alignment(0, 0),
                )
            )

        self.coluna_cartoes_dashboard.controls = cards_cartoes_ui

    def carregar_opcoes_cartoes(self):
        if not self.perfil_ativo_id[0]:
            return
        from database.crud import buscar_cartoes_do_perfil
        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        self.dropdown_cartao.options = [ft.dropdown.Option(key=str(c.id), text=c.nome) for c in cartoes]
        if self.dropdown_cartao.options and not self.dropdown_cartao.value:
            self.dropdown_cartao.value = self.dropdown_cartao.options[0].key

    def carregar_perfis_header(self):
        perfis = buscar_todos_perfis()
        self.dropdown_perfis_header.options = [ft.dropdown.Option(key=str(p.id), text=p.nome) for p in perfis]
        if self.perfil_ativo_id[0]:
            self.dropdown_perfis_header.value = str(self.perfil_ativo_id[0])
        self.dropdown_perfis_header.update()

    def adicionar_transacao(self, e=None):
        """Regista uma nova transação ou parcelamento no sistema."""
        if not self.perfil_ativo_id[0]:
            mostrar_mensagem(self.page_ref, "❌ Selecione um perfil primeiro!")
            return

        dt, val, desc, cartao_id, parcelas = self._get_dados_form()
        if not dt or val is None or not desc:
            mostrar_mensagem(self.page_ref, "❌ Preencha todos os campos obrigatórios corretamente!")
            return

        try:
            tipo = self.dropdown_tipo.value
            forma_pagamento = self.dropdown_pagamento.value

            salvar_transacao(
                descricao=desc,
                valor=val,
                tipo=tipo,
                forma_pagamento=forma_pagamento,
                data_dt=dt,
                perfil_id=self.perfil_ativo_id[0],
                cartao_id=cartao_id,
                parcelas=parcelas,
            )

            self.txt_descricao.value = ""
            self.txt_valor.value = ""
            self.txt_descricao.update()
            self.txt_valor.update()

            mostrar_mensagem(self.page_ref, "✅ Lançamento adicionado com sucesso!")
            self.carregar_dados()

        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao adicionar transação: {ex}")

    def _get_dados_form(self):
        """Recolhe e valida os dados preenchidos no formulário de lançamento."""
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

    def deletar_transacao_acao(self, transacao_id):
        if remover_transacao(transacao_id):
            mostrar_mensagem(self.page_ref, "✅ Transação removida!")
            self.carregar_dados()

    def abrir_gestao_cartoes(self):
        self.dialog_gestao_cartoes.abrir()

    def abrir_dialog_edicao(self, transacao):
        self.dialog_editar.abrir_para_edicao(transacao)

    def mudar_aba(self, nome_aba: str):
        self.aba_dashboard.visible = (nome_aba == "dashboard")
        self.aba_geral.visible = (nome_aba == "geral")
        self.aba_cartao_content.visible = (nome_aba == "cartao")
        self.row_formulario_lancamento.visible = (nome_aba in ["geral", "cartao"])
        self.btn_tab_dashboard.style = self._obter_estilo_aba(nome_aba == "dashboard")
        self.btn_tab_geral.style = self._obter_estilo_aba(nome_aba == "geral")
        self.btn_tab_cartao.style = self._obter_estilo_aba(nome_aba == "cartao")
        self.page_ref.update()

    def ao_filtrar_data(self, e=None):
        self.carregar_dados()

    def ao_mudar_perfil_header(self, e=None):
        if self.dropdown_perfis_header.value:
            self.perfil_ativo_id[0] = int(self.dropdown_perfis_header.value)
            self.carregar_dados()

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

    def _obter_estilo_aba(self, selecionada=False):
        return ft.ButtonStyle(
            color=ft.Colors.WHITE if selecionada else ft.Colors.GREY_400,
            bgcolor=ft.Colors.BLUE_900 if selecionada else None,
        )