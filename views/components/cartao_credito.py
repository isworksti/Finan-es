from datetime import date
import flet as ft

from database.crud import buscar_cartoes_do_perfil, remover_transacao, salvar_transacao
from views.components.tabelas_transacoes import gerar_linhas_tabela
from utils.ui_helpers import mostrar_mensagem


class AbaCartaoCredito(ft.Container):
    """Aba dedicada a lançamentos de cartão de crédito e histórico de faturas."""

    def __init__(
        self,
        page_ref,
        perfil_ativo_id,
        obter_periodo,
        on_atualizar,
        formatar_moeda_func,
        extrair_data_func,
        on_editar_transacao,
        on_abrir_gestao_cartoes,
    ):
        super().__init__(padding=10, visible=True, expand=True)
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.obter_periodo = obter_periodo
        self.on_atualizar = on_atualizar
        self.formatar = formatar_moeda_func
        self.extrair_data = extrair_data_func
        self.on_editar_transacao = on_editar_transacao
        self.on_abrir_gestao_cartoes = on_abrir_gestao_cartoes

        self._construir_ui()

    def _construir_ui(self):
        self.campo_busca = ft.TextField(
            label="Buscar",
            hint_text="Descrição...",
            text_size=12,
            height=40,
            expand=True,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            on_change=lambda e: self.on_atualizar(),
        )
        self.dropdown_forma = ft.Dropdown(
            label="Pagamento",
            text_size=12,
            height=40,
            width=160,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            options=[ft.dropdown.Option(o) for o in ["Todas", "Crédito"]],
            value="Todas",
            on_select=lambda e: self.on_atualizar(),
        )
        barra_filtros = ft.Row([self.campo_busca, self.dropdown_forma], spacing=10)

        self.btn_adicionar = ft.FilledButton(
            "Adicionar",
            icon=ft.Icons.ADD,
            height=40,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.abrir_formulario,
        )
        self.btn_fechar = ft.IconButton(
            icon=ft.Icons.CLOSE,
            tooltip="Fechar formulário",
            on_click=self.fechar_formulario,
        )

        self.txt_data = ft.TextField(
            label="Dia",
            value=f"{date.today().day:02d}",
            width=75,
            hint_text="DD",
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.txt_descricao = ft.TextField(
            label="Descrição",
            width=220,
            hint_text="Ex: Compra, assinatura...",
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.txt_valor = ft.TextField(
            label="Valor",
            width=130,
            hint_text="0,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.dropdown_tipo = ft.Dropdown(
            label="Tipo",
            width=130,
            value="Saída",
            options=[ft.dropdown.Option(o) for o in ["Saída", "Entrada"]],
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.dropdown_cartao = ft.Dropdown(
            label="Cartão",
            width=165,
            options=[],
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.chk_parcelado = ft.Checkbox(
            label="Parcelado?",
            value=False,
            on_change=self._ao_mudar_parcelado,
        )
        self.txt_num_parcelas = ft.TextField(
            label="Parcelas",
            value="2",
            width=90,
            hint_text="2",
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.btn_salvar = ft.FilledButton(
            "Salvar",
            icon=ft.Icons.SAVE,
            height=48,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar,
        )

        self.painel_formulario = ft.Column(
            [
                ft.Row([self.btn_fechar], alignment=ft.MainAxisAlignment.END),
                ft.Row(
                    [
                        self.txt_data,
                        self.txt_descricao,
                        self.txt_valor,
                        self.dropdown_tipo,
                        self.dropdown_cartao,
                        self.chk_parcelado,
                        self.txt_num_parcelas,
                        self.btn_salvar,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
            ],
            spacing=6,
            visible=False,
        )

        self.tabela = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(c))
                for c in ["Data", "Descrição", "Tipo", "Cartão", "Valor", "Ações"]
            ],
            rows=[],
        )

        header_cartao = ft.Row(
            [
                ft.Text("Histórico de Faturas e Cartões", size=18, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        self.btn_adicionar,
                        ft.TextButton(
                            "Gerenciar Cartões",
                            icon=ft.Icons.SETTINGS,
                            icon_color=ft.Colors.BLUE_400,
                            on_click=lambda e: self.on_abrir_gestao_cartoes(),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.content = ft.Column(
            [
                header_cartao,
                self.painel_formulario,
                barra_filtros,
                ft.Column(
                    [ft.Row([self.tabela], scroll=ft.ScrollMode.AUTO)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
            expand=True,
        )

    def obter_filtros(self):
        busca = (self.campo_busca.value or "").strip().lower()
        forma = self.dropdown_forma.value or "Todas"
        return busca, forma

    def carregar_cartoes(self):
        if not self.perfil_ativo_id[0]:
            return
        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        self.dropdown_cartao.options = [
            ft.dropdown.Option(key=str(c.id), text=c.nome) for c in cartoes
        ]
        if self.dropdown_cartao.options and not self.dropdown_cartao.value:
            self.dropdown_cartao.value = self.dropdown_cartao.options[0].key

    def abrir_formulario(self, e=None):
        self.carregar_cartoes()
        self.painel_formulario.visible = True
        self.btn_adicionar.visible = False
        if self.page_ref:
            self.page_ref.update()

    def fechar_formulario(self, e=None):
        self.painel_formulario.visible = False
        self.btn_adicionar.visible = True
        if self.page_ref:
            self.page_ref.update()

    def _ao_mudar_parcelado(self, e=None):
        self.txt_num_parcelas.visible = bool(self.chk_parcelado.value)
        if self.page_ref:
            self.page_ref.update()

    def salvar(self, e=None):
        if not self.perfil_ativo_id[0]:
            mostrar_mensagem(self.page_ref, "❌ Selecione um perfil primeiro!")
            return

        if not self.dropdown_cartao.value:
            mostrar_mensagem(self.page_ref, "❌ Cadastre ou selecione um cartão primeiro!")
            return

        try:
            mes, ano = self.obter_periodo()
            dia = int((self.txt_data.value or "").strip())
            dt = date(ano, mes, dia)

            val_str = (
                str(self.txt_valor.value or "")
                .replace("R$", "")
                .replace(" ", "")
                .replace(",", ".")
                .strip()
            )
            val = float(val_str)
            desc = (self.txt_descricao.value or "").strip()

            if not desc or val <= 0:
                mostrar_mensagem(self.page_ref, "❌ Preencha descrição e um valor maior que zero!")
                return

            parcelas = 1
            if self.chk_parcelado.value:
                parcelas_str = (self.txt_num_parcelas.value or "1").strip()
                parcelas = max(1, int(parcelas_str))

            salvar_transacao(
                descricao=desc,
                valor=val,
                tipo=self.dropdown_tipo.value or "Saída",
                forma_pagamento="Crédito",
                data_dt=dt,
                perfil_id=self.perfil_ativo_id[0],
                cartao_id=int(self.dropdown_cartao.value),
                parcelas=parcelas,
            )

            self.txt_descricao.value = ""
            self.txt_valor.value = ""
            self.chk_parcelado.value = False
            self.txt_num_parcelas.value = "2"
            self.txt_num_parcelas.visible = False
            self.painel_formulario.visible = False
            self.btn_adicionar.visible = True

            mostrar_mensagem(self.page_ref, "✅ Compra no cartão registrada com sucesso!")
            self.on_atualizar()
        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao salvar compra no cartão: {ex}")
 
    def _excluir(self, transacao_id):
        if remover_transacao(transacao_id):
            mostrar_mensagem(self.page_ref, "✅ Transação removida!")
            self.on_atualizar()

    def atualizar(self, dados: dict):
        self.carregar_cartoes()
        self.tabela.rows = gerar_linhas_tabela(
            dados.get("tc_mes", []),
            self.on_editar_transacao,
            self._excluir,
            self.extrair_data,
            self.formatar,
            modo_cartao=True,
            mapa_cartoes=dados.get("mapa_cartoes", {}),
        )