import flet as ft
from database.crud import (
    buscar_cartoes_do_perfil,
    salvar_cartao,
    deletar_cartao,
)
from utils.ui_helpers import mostrar_mensagem


class GestaoCartoesDialog(ft.AlertDialog):
    def __init__(self, page_ref: ft.Page, perfil_ativo_id, on_atualizar_dados_dashboard=None):
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.on_atualizar_dados_dashboard = on_atualizar_dados_dashboard
        self.cartao_em_edicao_id = None

        # Campos do Formulário
        self.txt_nome = ft.TextField(label="Nome do Cartão", expand=True)
        self.txt_limite = ft.TextField(
            label="Limite (R$)",
            width=140,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.txt_fechamento = ft.TextField(
            label="Dia Fechamento",
            width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="Ex: 5",
        )
        self.txt_vencimento = ft.TextField(
            label="Dia Vencimento",
            width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="Ex: 12",
        )

        self.btn_salvar = ft.FilledButton(
            "Salvar Cartão",
            icon=ft.Icons.SAVE,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar_cartao_acao,
        )

        # Tabela simplificada (sem a coluna de Limites e Visão Geral)
        self.tabela_cartoes = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cartão")),
                ft.DataColumn(ft.Text("Limite Cadastrado")),
                ft.DataColumn(ft.Text("Fechamento")),
                ft.DataColumn(ft.Text("Vencimento")),
                ft.DataColumn(ft.Text("Ações")),
            ],
            rows=[],
        )

        super().__init__(
            title=ft.Text("Gerenciamento de Cartões de Crédito"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Cadastrar / Editar Cartão", weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
                                self.txt_nome,
                                self.txt_limite,
                                self.txt_fechamento,
                                self.txt_vencimento,
                                self.btn_salvar,
                            ],
                            spacing=10,
                        ),
                        ft.Divider(),
                        ft.Text("Cartões Cadastrados", weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=self.tabela_cartoes,
                            expand=True,
                        ),
                    ],
                    spacing=15,
                    tight=True,
                ),
                width=800,
                height=450,
            ),
            actions=[
                ft.TextButton("Fechar", on_click=lambda e: self.fechar()),
            ],
        )

    def abrir(self):
        self.limpar_formulario()
        self.atualizar_tabela_cartoes()
        self.open = True
        self.page_ref.update()

    def fechar(self):
        self.open = False
        self.page_ref.update()
        if self.on_atualizar_dados_dashboard:
            self.on_atualizar_dados_dashboard()

    def limpar_formulario(self):
        self.cartao_em_edicao_id = None
        self.txt_nome.value = ""
        self.txt_limite.value = ""
        self.txt_fechamento.value = ""
        self.txt_vencimento.value = ""
        self.btn_salvar.text = "Salvar Cartão"

    def preencher_formulario_edicao(self, cartao):
        self.cartao_em_edicao_id = cartao.id
        self.txt_nome.value = cartao.nome
        self.txt_limite.value = str(cartao.limite)
        self.txt_fechamento.value = str(cartao.dia_fechamento)
        self.txt_vencimento.value = str(cartao.dia_vencimento)
        self.btn_salvar.text = "Atualizar"
        self.page_ref.update()

    def atualizar_tabela_cartoes(self):
        """Preenche a tabela com as colunas essenciais e limpas."""
        if not self.perfil_ativo_id[0]:
            return

        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        linhas = []

        for cartao in cartoes:
            btn_edit = ft.IconButton(
                icon=ft.Icons.EDIT,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Editar",
                on_click=lambda e, c=cartao: self.preencher_formulario_edicao(c),
            )
            btn_del = ft.IconButton(
                icon=ft.Icons.DELETE,
                icon_color=ft.Colors.RED_400,
                tooltip="Excluir",
                on_click=lambda e, c_id=cartao.id: self.deletar_cartao_acao(c_id),
            )

            limite_fmt = f"R$ {cartao.limite:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            linhas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(cartao.nome, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(limite_fmt)),
                        ft.DataCell(ft.Text(f"Dia {cartao.dia_fechamento}")),
                        ft.DataCell(ft.Text(f"Dia {cartao.dia_vencimento}")),
                        ft.DataCell(ft.Row([btn_edit, btn_del], spacing=0)),
                    ]
                )
            )

        self.tabela_cartoes.rows = linhas
        self.page_ref.update()

    def salvar_cartao_acao(self, e):
        nome = self.txt_nome.value.strip() if self.txt_nome.value else ""
        limite_str = self.txt_limite.value.replace("R$", "").replace(",", ".").strip() if self.txt_limite.value else "0"
        fech_str = self.txt_fechamento.value.strip() if self.txt_fechamento.value else "0"
        venc_str = self.txt_vencimento.value.strip() if self.txt_vencimento.value else "0"

        if not nome or not fech_str.isdigit() or not venc_str.isdigit():
            mostrar_mensagem(self.page_ref, "❌ Preencha os campos corretamente!")
            return

        try:
            limite = float(limite_str)
            dia_fechamento = int(fech_str)
            dia_vencimento = int(venc_str)

            salvar_cartao(
                cartao_id=self.cartao_em_edicao_id,
                nome=nome,
                limite=limite,
                dia_fechamento=dia_fechamento,
                dia_vencimento=dia_vencimento,
                perfil_id=self.perfil_ativo_id[0],
            )

            mostrar_mensagem(self.page_ref, "✅ Cartão salvo com sucesso!")
            self.limpar_formulario()
            self.atualizar_tabela_cartoes()

        except Exception as ex:
            print(f"Erro ao salvar cartão: {ex}")

    def deletar_cartao_acao(self, cartao_id):
        if deletar_cartao(cartao_id):
            mostrar_mensagem(self.page_ref, "Cartão removido!")
            self.atualizar_tabela_cartoes()