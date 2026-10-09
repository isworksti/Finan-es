import flet as ft
from database.crud import buscar_cartoes_do_perfil, remover_cartao, salvar_cartao
from utils.ui_helpers import mostrar_mensagem

class GestaoCartoesDialog(ft.AlertDialog):
    def __init__(self, page_ref: ft.Page, perfil_ativo_id, on_atualizar_dados_dashboard):
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.on_atualizar_dados_dashboard = on_atualizar_dados_dashboard

        # --- CAMPOS DE ENTRADA DE DADOS ---
        self.txt_nome = ft.TextField(
            hint_text="Ex: Nubank, Itaú",
            expand=True,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=12)
        )
        self.txt_limite = ft.TextField(
            hint_text="Ex: 5000.00",
            width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=12)
        )
        self.txt_fechamento = ft.TextField(
            hint_text="Dia (Ex: 5)",
            width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=12)
        )
        self.txt_vencimento = ft.TextField(
            hint_text="Dia (Ex: 12)",
            width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=12)
        )

        self.tabela_cartoes = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nome")),
                ft.DataColumn(ft.Text("Limite (R$)")),
                ft.DataColumn(ft.Text("Fechamento")),
                ft.DataColumn(ft.Text("Vencimento")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            rows=[],
        )

        # Helper para criar rótulos pequenos acima dos campos
        def criar_campo_com_label(label_texto, campo_control):
            return ft.Column(
                [
                    ft.Text(label_texto, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
                    campo_control
                ],
                spacing=4,
                tight=True
            )

        btn_salvar = ft.FilledButton(
            "Salvar Cartão",
            icon=ft.Icons.SAVE,
            height=46,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar_novo_cartao,
        )

        super().__init__(
            title=ft.Text("Gerenciamento de Cartões de Crédito"),
            content=ft.Container(
                width=680,
                height=450,
                content=ft.Column(
                    [
                        ft.Text("Cadastrar / Adicionar Cartão", weight=ft.FontWeight.BOLD, size=14),
                        # Formulário distribuído uniformemente em uma linha com rótulos acima
                        ft.Row(
                            [
                                ft.Container(content=criar_campo_com_label("Nome do Cartão", self.txt_nome), expand=True),
                                criar_campo_com_label("Limite (R$)", self.txt_limite),
                                criar_campo_com_label("Fechamento", self.txt_fechamento),
                                criar_campo_com_label("Vencimento", self.txt_vencimento),
                                ft.Column(
                                    [
                                        ft.Container(height=18), # Alinha o botão com a base dos inputs
                                        btn_salvar
                                    ],
                                    tight=True,
                                    spacing=0
                                )
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        ft.Divider(),
                        ft.Text("Cartões Cadastrados", weight=ft.FontWeight.BOLD, size=14),
                        ft.Column([self.tabela_cartoes], scroll=ft.ScrollMode.AUTO, expand=True),
                    ],
                    tight=True,
                    spacing=12,
                ),
            ),
            actions=[
                ft.TextButton("Fechar", on_click=lambda e: self.fechar())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def carregar_tabela(self):
        if not self.perfil_ativo_id[0]:
            return

        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        linhas = []

        for c in cartoes:
            btn_del = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINED,
                icon_color=ft.Colors.RED_400,
                tooltip="Remover Cartão",
                on_click=lambda e, cartao_id=c.id: self.excluir_cartao(cartao_id),
            )

            linhas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(c.nome)),
                        ft.DataCell(ft.Text(f"R$ {c.limite:.2f}")),
                        ft.DataCell(ft.Text(str(c.dia_fechamento or "-"))),
                        ft.DataCell(ft.Text(str(c.dia_vencimento or "-"))),
                        ft.DataCell(btn_del),
                    ]
                )
            )

        self.tabela_cartoes.rows = linhas
        if self.page:
            self.page.update()

    def salvar_novo_cartao(self, e):
        try:
            nome = self.txt_nome.value.strip() if self.txt_nome.value else ""
            limite = float(self.txt_limite.value.replace(",", ".")) if self.txt_limite.value else 0.0
            fechamento = int(self.txt_fechamento.value.strip()) if self.txt_fechamento.value else 1
            vencimento = int(self.txt_vencimento.value.strip()) if self.txt_vencimento.value else 10

            if not nome or limite <= 0:
                mostrar_mensagem(self.page_ref, "❌ Preencha o nome e limite corretamente!")
                return

            salvar_cartao(
                nome=nome,
                limite=limite,
                dia_fechamento=fechamento,
                dia_vencimento=vencimento,
                perfil_id=self.perfil_ativo_id[0],
            )

            self.txt_nome.value = ""
            self.txt_limite.value = ""
            self.txt_fechamento.value = ""
            self.txt_vencimento.value = ""

            mostrar_mensagem(self.page_ref, "✅ Cartão cadastrado com sucesso!")
            self.carregar_tabela()
            self.on_atualizar_dados_dashboard()

        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao salvar cartão: {ex}")

    def excluir_cartao(self, cartao_id):
        if remover_cartao(cartao_id):
            mostrar_mensagem(self.page_ref, "✅ Cartão removido!")
            self.carregar_tabela()
            self.on_atualizar_dados_dashboard()

    def abrir(self):
        self.carregar_tabela()
        self.open = True
        if self.page:
            self.page.update()

    def fechar(self):
        self.open = False
        self.txt_nome.value = ""
        self.txt_limite.value = ""
        self.txt_fechamento.value = ""
        self.txt_vencimento.value = ""
        if self.page:
            self.page.update()