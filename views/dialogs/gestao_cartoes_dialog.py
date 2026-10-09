import flet as ft
from datetime import datetime
from database.crud import (
    buscar_cartoes_do_perfil,
    remover_cartao,
    salvar_cartao,
    atualizar_cartao,             # Função no seu CRUD para atualizar
    buscar_historico_limite       # Função no seu CRUD para consultar histórico
)
from utils.ui_helpers import mostrar_mensagem

class GestaoCartoesDialog(ft.AlertDialog):
    def __init__(self, page_ref: ft.Page, perfil_ativo_id, on_atualizar_dados_dashboard):
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.on_atualizar_dados_dashboard = on_atualizar_dados_dashboard
        
        # Controle para saber se estamos editando um cartão existente
        self.cartao_em_edicao_id = None
        self.limite_atual_em_edicao = 0.0

        padding_campos = ft.Padding(left=12, right=12, top=12, bottom=12)

        # --- CAMPOS DO FORMULÁRIO ---
        self.txt_nome = ft.TextField(
            hint_text="Ex: Nubank, Itaú",
            expand=True,
            content_padding=padding_campos
        )
        self.txt_limite = ft.TextField(
            hint_text="Ex: 5000.00",
            width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=padding_campos,
            on_change=self._verificar_mudanca_limite
        )
        self.txt_fechamento = ft.TextField(
            hint_text="Dia (Ex: 5)",
            width=110,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=padding_campos
        )
        self.txt_vencimento = ft.TextField(
            hint_text="Dia (Ex: 12)",
            width=110,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=padding_campos
        )
        # Campo para anotação da mudança de limite (visível apenas na edição de limite)
        self.txt_motivo_limite = ft.TextField(
            hint_text="Ex: Aumento concedido pelo banco / Solicitado no app",
            expand=True,
            content_padding=padding_campos,
            visible=False
        )

        self.lbl_motivo = ft.Text(
            "Anotação / Motivo da alteração do limite:",
            size=12,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.GREY_400,
            visible=False
        )

        self.btn_salvar = ft.FilledButton(
            "Salvar Cartão",
            icon=ft.Icons.SAVE,
            height=46,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar_ou_atualizar_cartao,
        )

        self.btn_cancelar_edicao = ft.OutlinedButton(
            "Cancelar Edição",
            height=46,
            visible=False,
            on_click=lambda e: self.limpar_formulario()
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

        def criar_campo_com_label(label_texto, campo_control):
            return ft.Column(
                [
                    ft.Text(label_texto, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_400),
                    campo_control
                ],
                spacing=4,
                tight=True
            )

        super().__init__(
            title=ft.Text("Gerenciamento de Cartões de Crédito"),
            content=ft.Container(
                width=720,
                height=500,
                content=ft.Column(
                    [
                        ft.Text("Cadastrar / Editar Cartão", weight=ft.FontWeight.BOLD, size=14),
                        # Linha principal de inputs
                        ft.Row(
                            [
                                ft.Container(content=criar_campo_com_label("Nome do Cartão", self.txt_nome), expand=True),
                                criar_campo_com_label("Limite (R$)", self.txt_limite),
                                criar_campo_com_label("Fechamento", self.txt_fechamento),
                                criar_campo_com_label("Vencimento", self.txt_vencimento),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        # Linha para o motivo do limite (aparece dinamicamente se o limite for alterado)
                        ft.Column(
                            [
                                self.lbl_motivo,
                                self.txt_motivo_limite,
                            ],
                            spacing=4,
                            tight=True
                        ),
                        ft.Row(
                            [
                                self.btn_cancelar_edicao,
                                self.btn_salvar,
                            ],
                            alignment=ft.MainAxisAlignment.END,
                            spacing=10
                        ),
                        ft.Divider(),
                        ft.Text("Cartões Cadastrados", weight=ft.FontWeight.BOLD, size=14),
                        ft.Column([self.tabela_cartoes], scroll=ft.ScrollMode.AUTO, expand=True),
                    ],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton("Fechar", on_click=lambda e: self.fechar())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _verificar_mudanca_limite(self, e=None):
        """Exibe o campo de anotação apenas se estiver editando e o valor do limite for alterado."""
        if self.cartao_em_edicao_id:
            try:
                novo_limite = float(self.txt_limite.value.replace(",", ".")) if self.txt_limite.value else 0.0
                limite_mudou = abs(novo_limite - self.limite_atual_em_edicao) > 0.01
                self.lbl_motivo.visible = limite_mudou
                self.txt_motivo_limite.visible = limite_mudou
                if self.page:
                    self.page.update()
            except ValueError:
                pass

    def carregar_tabela(self):
        if not self.perfil_ativo_id[0]:
            return

        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        linhas = []

        for c in cartoes:
            btn_edit = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Editar Cartão",
                on_click=lambda e, cartao=c: self.preparar_edicao(cartao)
            )
            btn_hist = ft.IconButton(
                icon=ft.Icons.HISTORY,
                icon_color=ft.Colors.AMBER_400,
                tooltip="Histórico de Limites",
                on_click=lambda e, cartao_id=c.id, nome=c.nome: self.exibir_historico_limite(cartao_id, nome)
            )
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
                        ft.DataCell(ft.Row([btn_edit, btn_hist, btn_del], spacing=0)),
                    ]
                )
            )

        self.tabela_cartoes.rows = linhas
        if self.page:
            self.page.update()

    def preparar_edicao(self, cartao):
        """Preenche o formulário para editar o cartão selecionado."""
        self.cartao_em_edicao_id = cartao.id
        self.limite_atual_em_edicao = cartao.limite

        self.txt_nome.value = cartao.nome
        self.txt_limite.value = f"{cartao.limite:.2f}".replace(".", ",")
        self.txt_fechamento.value = str(cartao.dia_fechamento or "")
        self.txt_vencimento.value = str(cartao.dia_vencimento or "")
        
        self.btn_salvar.text = "Atualizar Cartão"
        self.btn_cancelar_edicao.visible = True

        self._verificar_mudanca_limite()
        if self.page:
            self.page.update()

    def limpar_formulario(self):
        self.cartao_em_edicao_id = None
        self.limite_atual_em_edicao = 0.0

        self.txt_nome.value = ""
        self.txt_limite.value = ""
        self.txt_fechamento.value = ""
        self.txt_vencimento.value = ""
        self.txt_motivo_limite.value = ""

        self.lbl_motivo.visible = False
        self.txt_motivo_limite.visible = False

        self.btn_salvar.text = "Salvar Cartão"
        self.btn_cancelar_edicao.visible = False

        if self.page:
            self.page.update()

    def salvar_ou_atualizar_cartao(self, e):
        try:
            nome = self.txt_nome.value.strip() if self.txt_nome.value else ""
            limite = float(self.txt_limite.value.replace(",", ".")) if self.txt_limite.value else 0.0
            fechamento = int(self.txt_fechamento.value.strip()) if self.txt_fechamento.value else 1
            vencimento = int(self.txt_vencimento.value.strip()) if self.txt_vencimento.value else 10
            anotacao = self.txt_motivo_limite.value.strip() if self.txt_motivo_limite.value else "Ajuste de limite"

            if not nome or limite <= 0:
                mostrar_mensagem(self.page_ref, "❌ Preencha o nome e limite corretamente!")
                return

            if self.cartao_em_edicao_id:
                # Atualização do Cartão Existente
                atualizar_cartao(
                    cartao_id=self.cartao_em_edicao_id,
                    nome=nome,
                    limite=limite,
                    dia_fechamento=fechamento,
                    dia_vencimento=vencimento,
                    anotacao_limite=anotacao if self.txt_motivo_limite.visible else None
                )
                mostrar_mensagem(self.page_ref, "✅ Cartão atualizado com sucesso!")
            else:
                # Novo Cartão
                salvar_cartao(
                    nome=nome,
                    limite=limite,
                    dia_fechamento=fechamento,
                    dia_vencimento=vencimento,
                    perfil_id=self.perfil_ativo_id[0],
                )
                mostrar_mensagem(self.page_ref, "✅ Cartão cadastrado com sucesso!")

            self.limpar_formulario()
            self.carregar_tabela()
            self.on_atualizar_dados_dashboard()

        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao salvar/atualizar cartão: {ex}")

    def exibir_historico_limite(self, cartao_id, nome_cartao):
        """Abre um diálogo exibindo o histórico de alterações de limite do cartão."""
        historico = buscar_historico_limite(cartao_id)
        
        linhas = []
        for h in historico:
            data_fmt = h.data_alteracao.strftime("%d/%m/%Y %H:%M") if hasattr(h, "data_alteracao") and h.data_alteracao else "-"
            linhas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(data_fmt)),
                        ft.DataCell(ft.Text(f"R$ {h.limite_anterior:.2f}")),
                        ft.DataCell(ft.Text(f"R$ {h.limite_novo:.2f}")),
                        ft.DataCell(ft.Text(h.anotacao or "-")),
                    ]
                )
            )

        tabela_hist = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Data")),
                ft.DataColumn(ft.Text("Anterior")),
                ft.DataColumn(ft.Text("Novo Limite")),
                ft.DataColumn(ft.Text("Anotação")),
            ],
            rows=linhas
        )

        dialog_hist = ft.AlertDialog(
            title=ft.Text(f"Histórico de Limites - {nome_cartao}"),
            content=ft.Container(
                width=550,
                height=300,
                content=ft.Column([tabela_hist], scroll=ft.ScrollMode.AUTO, expand=True)
            ),
            actions=[ft.TextButton("Fechar", on_click=lambda e: setattr(dialog_hist, "open", False) or self.page_ref.update())]
        )

        self.page_ref.overlay.append(dialog_hist)
        dialog_hist.open = True
        self.page_ref.update()

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
        self.limpar_formulario()
        if self.page:
            self.page.update()