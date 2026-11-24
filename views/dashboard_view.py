from datetime import date, datetime
import flet as ft
import flet_charts as fch

from database.crud import (
    MAPA_MESES,
    MESES,
    buscar_todos_perfis,
    obter_ou_criar_fatura_mensal,
    atualizar_status_fatura,
    calcular_limites_cartao,
)
from services.fatura_service import projetar_faturas_futuras, obter_mes_ano_fatura
from controllers.dashboard_controller import DashboardController
from views.dialogs.gestao_cartoes_dialog import GestaoCartoesDialog
from views.dialogs.editar_transacao_dialog import EditarTransacaoDialog

from utils.date_utils import extrair_data
from utils.ui_helpers import mostrar_mensagem

# Componentes modularizados
from views.components.kpi_cards import criar_linha_kpis
from views.components.cartao_card import criar_card_cartao
from views.components.contas_recorrentes import AbaContasRecorrentes, GraficoRendaComprometida
from views.components.lancamentos_gerais import AbaLancamentosGerais
from views.components.cartao_credito import AbaCartaoCredito


def formatar_moeda(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DashboardView(ft.Column):
    def __init__(self, page: ft.Page, perfil_ativo_id, on_trocar_perfil):
        super().__init__(expand=True, visible=False)
        self.page_ref = page
        self.perfil_ativo_id = perfil_ativo_id
        self.on_trocar_perfil_cb = on_trocar_perfil
        self.aba_atual = "dashboard"

        self.controller = DashboardController(perfil_ativo_id)

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

        self._construir_controles_ui()
        self._construir_layout_principal()

    def _make_dd(self, label, options, value=None, width=None, expand=False, on_select=None):
        opts = [
            ft.dropdown.Option(str(o[0]), text=str(o[1])) if isinstance(o, tuple) else ft.dropdown.Option(str(o))
            for o in options
        ]
        return ft.Dropdown(
            label=label,
            width=width,
            expand=expand,
            value=value,
            options=opts,
            on_select=on_select,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
            menu_height=200,
        )

    def _txt_kpi(self, color):
        return ft.Text("R$ 0,00", size=20, weight=ft.FontWeight.BOLD, color=color)

    def _construir_controles_ui(self):
        self.dropdown_filtro_mes = self._make_dd(
            "Mês da Fatura",
            MESES,
            value=str(datetime.now().month),
            width=160,
            on_select=self.ao_filtrar_data,
        )
        self.dropdown_filtro_ano = self._make_dd(
            "Ano",
            [str(y) for y in range(2024, 2028)],
            value=str(datetime.now().year),
            width=110,
            on_select=self.ao_filtrar_data,
        )
        self.dropdown_perfis_header = self._make_dd(
            "Perfil Ativo",
            [],
            width=170,
            on_select=self.ao_mudar_perfil_header,
        )

        self.avatar_perfil_header = ft.CircleAvatar(
            radius=16,
            bgcolor=ft.Colors.BLUE_700,
            content=ft.Text("P", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        )
        self.txt_nome_perfil_header = ft.Text(
            "Perfil", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
        )
        self.container_perfil_header = ft.Row(
            [self.avatar_perfil_header, self.txt_nome_perfil_header],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Controles exclusivos da aba Dashboard
        self.txt_kpi_entradas = self._txt_kpi(ft.Colors.GREEN_400)
        self.txt_kpi_saidas = self._txt_kpi(ft.Colors.RED_400)
        self.txt_kpi_saldo = self._txt_kpi(ft.Colors.BLUE_400)
        self.txt_fatura_total = self._txt_kpi(ft.Colors.AMBER_400)
        self.chart_geral = fch.PieChart(sections=[], sections_space=2, center_space_radius=40)
        self.coluna_cartoes_dashboard = ft.Column(spacing=15, width=340, scroll=ft.ScrollMode.AUTO)
        self.grafico_comprometida = GraficoRendaComprometida(formatar_moeda)

        # Botões de navegação entre abas
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
        self.btn_tab_contas = ft.OutlinedButton(
            "Contas Recorrentes",
            icon=ft.Icons.REPEAT,
            style=self._obter_estilo_aba(False),
            on_click=lambda e: self.mudar_aba("contas"),
        )

        # Abas modulares
        self.aba_dashboard = self._criar_aba_dashboard()
        self.aba_geral = AbaLancamentosGerais(
            page_ref=self.page_ref,
            perfil_ativo_id=self.perfil_ativo_id,
            obter_periodo=self._obter_periodo,
            on_atualizar=self.carregar_dados,
            formatar_moeda_func=formatar_moeda,
            extrair_data_func=extrair_data,
            on_editar_transacao=self.abrir_dialog_edicao,
        )
        self.aba_cartao_content = AbaCartaoCredito(
            page_ref=self.page_ref,
            perfil_ativo_id=self.perfil_ativo_id,
            obter_periodo=self._obter_periodo,
            on_atualizar=self.carregar_dados,
            formatar_moeda_func=formatar_moeda,
            extrair_data_func=extrair_data,
            on_editar_transacao=self.abrir_dialog_edicao,
            on_abrir_gestao_cartoes=self.abrir_gestao_cartoes,
        )
        self.aba_contas = AbaContasRecorrentes(
            page_ref=self.page_ref,
            perfil_ativo_id=self.perfil_ativo_id,
            obter_periodo=self._obter_periodo,
            on_atualizar=self.carregar_dados,
            formatar_moeda_func=formatar_moeda,
        )
        self.aba_contas.expand = True

    def _criar_aba_dashboard(self):
        cards_kpi = criar_linha_kpis(
            self.txt_kpi_entradas,
            self.txt_kpi_saidas,
            self.txt_kpi_saldo,
            self.txt_fatura_total,
        )

        def make_chart_box(title, chart):
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(title, size=15, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=chart,
                            width=300,
                            height=220,
                            alignment=ft.Alignment(0, 0),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=15,
                height=290,
                border=ft.Border.all(1, ft.Colors.WHITE_24),
                border_radius=10,
                expand=True,
            )

        container_cartoes_lateral = ft.Container(
            content=self.coluna_cartoes_dashboard,
            height=290,
            width=330,
            padding=0,
        )

        graficos_row = ft.Row(
            [
                make_chart_box("Entradas x Saídas", self.chart_geral),
                self.grafico_comprometida,
                container_cartoes_lateral,
            ],
            spacing=15,
            expand=False,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        return ft.Container(
            content=ft.Column(
                [cards_kpi, ft.Container(height=15), graficos_row],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            padding=10,
            visible=True,
            expand=True,
        )

    def _construir_layout_principal(self):
        self.container_aba_ativa = ft.Container(
            content=self.aba_dashboard,
            expand=True,
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
                            self.container_perfil_header,
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
                    self.btn_tab_contas,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(),
            self.container_aba_ativa,
        ]

    def mudar_aba(self, nome_aba: str):
        mapa_abas = {
            "dashboard": self.aba_dashboard,
            "geral": self.aba_geral,
            "cartao": self.aba_cartao_content,
            "contas": self.aba_contas,
        }
        self.aba_atual = nome_aba if nome_aba in mapa_abas else "dashboard"
        aba_escolhida = mapa_abas[self.aba_atual]

        for chave, aba in mapa_abas.items():
            aba.visible = chave == self.aba_atual

        self.container_aba_ativa.content = aba_escolhida

        self.btn_tab_dashboard.style = self._obter_estilo_aba(self.aba_atual == "dashboard")
        self.btn_tab_geral.style = self._obter_estilo_aba(self.aba_atual == "geral")
        self.btn_tab_cartao.style = self._obter_estilo_aba(self.aba_atual == "cartao")
        self.btn_tab_contas.style = self._obter_estilo_aba(self.aba_atual == "contas")

        self.carregar_dados()
        if self.page_ref:
            self.page_ref.update()

    def _obter_filtros_ativos(self):
        if self.aba_atual == "cartao":
            return self.aba_cartao_content.obter_filtros()
        return self.aba_geral.obter_filtros()

    def carregar_dados(self):
        if not self.perfil_ativo_id[0]:
            if self.page_ref:
                self.page_ref.update()
            return

        try:
            mes_sel, ano_sel = self._obter_periodo()
            texto_busca, forma_sel = self._obter_filtros_ativos()

            dados = self.controller.obter_dados_filtrados(mes_sel, ano_sel, texto_busca, forma_sel)
            if not dados:
                if self.page_ref:
                    self.page_ref.update()
                return

            self.atualizar_dashboard(dados, mes_sel, ano_sel)
            self.aba_geral.atualizar(dados)
            self.aba_cartao_content.atualizar(dados)
            self.aba_contas.atualizar(dados)

            if self.page_ref:
                self.page_ref.update()

        except Exception as ex:
            import traceback
            traceback.print_exc()
            mostrar_mensagem(self.page_ref, f"❌ Erro ao carregar dados: {ex}")

    def atualizar_dashboard(self, dados, mes_sel, ano_sel):
        self._atualizar_kpis(dados)
        self._atualizar_grafico_geral(dados)
        self._atualizar_cards_cartoes(dados, mes_sel, ano_sel)
        if "comprometimento" in dados:
            self.grafico_comprometida.atualizar(dados["comprometimento"])

    def _obter_periodo(self):
        mes_sel = (
            int(self.dropdown_filtro_mes.value)
            if str(self.dropdown_filtro_mes.value).isdigit()
            else MAPA_MESES.get(str(self.dropdown_filtro_mes.value), date.today().month)
        )
        ano_sel = int(self.dropdown_filtro_ano.value or date.today().year)
        return mes_sel, ano_sel

    def _atualizar_kpis(self, dados):
        total_entradas = dados["total_entradas"]
        total_saidas = dados["total_saidas"]
        saldo_mes = dados["saldo_mes"]

        self.txt_kpi_entradas.value = formatar_moeda(total_entradas)
        self.txt_kpi_saidas.value = formatar_moeda(total_saidas)
        self.txt_kpi_saldo.value = formatar_moeda(saldo_mes)
        self.txt_kpi_saldo.color = ft.Colors.GREEN_400 if saldo_mes >= 0 else ft.Colors.RED_400
        self.txt_fatura_total.value = formatar_moeda(dados["fatura_mes_total"])

    def _atualizar_grafico_geral(self, dados):
        tot_geral = dados["total_entradas"] + dados["total_saidas"]
        if tot_geral > 0:
            self.chart_geral.sections = [
                fch.PieChartSection(
                    value=dados["total_entradas"] or 0.001,
                    title=f"Entradas\n{(dados['total_entradas']/tot_geral)*100:.1f}%",
                    color=ft.Colors.BLUE_400,
                    radius=55,
                    title_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ),
                fch.PieChartSection(
                    value=dados["total_saidas"] or 0.001,
                    title=f"Saídas\n{(dados['total_saidas']/tot_geral)*100:.1f}%",
                    color=ft.Colors.RED_400,
                    radius=55,
                    title_style=ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ),
            ]
        else:
            self.chart_geral.sections = [
                fch.PieChartSection(
                    value=1.0,
                    title="Sem dados",
                    color=ft.Colors.GREY_700,
                    radius=55,
                    title_style=ft.TextStyle(size=11, color=ft.Colors.WHITE),
                )
            ]

    def _atualizar_cards_cartoes(self, dados, mes_sel, ano_sel):
        cards_cartoes_ui = []
        for cartao in dados["cartoes_lista"]:
            card_container = criar_card_cartao(
                page_ref=self.page_ref,
                cartao=cartao,
                mes_sel=mes_sel,
                ano_sel=ano_sel,
                transacoes_todas=dados["transacoes_todas"],
                mapa_cartoes=dados["mapa_cartoes"],
                on_atualizar_dados=self.carregar_dados,
                formatar_moeda_func=formatar_moeda,
                mostrar_mensagem_func=mostrar_mensagem,
                obter_ou_criar_fatura_mensal_func=obter_ou_criar_fatura_mensal,
                atualizar_status_fatura_func=atualizar_status_fatura,
                calcular_limites_cartao_func=calcular_limites_cartao,
                projetar_faturas_futuras_func=projetar_faturas_futuras,
                obter_mes_ano_fatura_func=obter_mes_ano_fatura,
                MESES_LISTA=MESES,
            )
            cards_cartoes_ui.append(card_container)

        if not cards_cartoes_ui:
            cards_cartoes_ui.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.CREDIT_CARD_OFF, size=40, color=ft.Colors.GREY_500),
                            ft.Text("Nenhum cartão cadastrado", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
                            ft.ElevatedButton("Cadastrar Cartão", icon=ft.Icons.ADD, on_click=lambda e: self.abrir_gestao_cartoes()),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    padding=20,
                    border=ft.Border.all(1, ft.Colors.WHITE_12),
                    border_radius=10,
                    width=320,
                    alignment=ft.Alignment(0, 0),
                )
            )

        self.coluna_cartoes_dashboard.controls = cards_cartoes_ui

    def carregar_perfis_header(self):
        perfis = buscar_todos_perfis()
        perfil_atual = next((p for p in perfis if p.id == self.perfil_ativo_id[0]), None)
        if perfil_atual:
            self.txt_nome_perfil_header.value = perfil_atual.nome
            foto_path = getattr(perfil_atual, "foto", None) or getattr(perfil_atual, "foto_path", None) or getattr(perfil_atual, "avatar", None)
            if foto_path:
                self.avatar_perfil_header.foreground_image_src = foto_path
                self.avatar_perfil_header.content = None
            else:
                self.avatar_perfil_header.foreground_image_src = None
                iniciais = "".join(parte[0] for parte in (perfil_atual.nome or "P").split()[:2]).upper()
                self.avatar_perfil_header.content = ft.Text(
                    iniciais or "P", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                )

    def abrir_gestao_cartoes(self):
        self.dialog_gestao_cartoes.abrir()

    def abrir_dialog_edicao(self, transacao):
        self.dialog_editar.abrir_para_edicao(transacao)

    def ao_filtrar_data(self, e=None):
        self.carregar_dados()

    def ao_mudar_perfil_header(self, e=None):
        if self.dropdown_perfis_header.value:
            self.perfil_ativo_id[0] = int(self.dropdown_perfis_header.value)
            self.carregar_dados()

    def _obter_estilo_aba(self, selecionada=False):
        return ft.ButtonStyle(
            color=ft.Colors.WHITE if selecionada else ft.Colors.GREY_400,
            bgcolor=ft.Colors.BLUE_900 if selecionada else None,
        )