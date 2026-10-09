import flet as ft
from database.crud import buscar_todos_perfis, criar_novo_perfil
from utils.ui_helpers import abrir_dialogo, fechar_dialogo, mostrar_mensagem

CORES_AVATAR = [
    ft.Colors.BLUE_600,
    ft.Colors.PURPLE_600,
    ft.Colors.GREEN_600,
    ft.Colors.AMBER_700,
    ft.Colors.RED_600,
    ft.Colors.TEAL_600,
    ft.Colors.INDIGO_600,
]

class SelecaoPerfilView(ft.Column):
    def __init__(self, page: ft.Page, on_selecionar):
        super().__init__(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            visible=True,
        )
        self.page_ref = page
        self.on_selecionar = on_selecionar

        self.row_perfis = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=30, wrap=True)
        self.txt_novo_nome_perfil = ft.TextField(
            label="Nome do Perfil", hint_text="Ex: João, Pessoal...", width=250
        )

        self.dlg_criar_perfil = ft.AlertDialog(
            modal=True,
            title=ft.Text("Criar Novo Perfil"),
            content=ft.Column([self.txt_novo_nome_perfil], tight=True),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: fechar_dialogo(self.page_ref, self.dlg_criar_perfil),
                ),
                ft.FilledButton("Criar", on_click=self.salvar_perfil),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.controls = [
            ft.Text("Quem está usando?", size=36, weight=ft.FontWeight.BOLD),
            ft.Container(height=30),
            self.row_perfis,
        ]

    def carregar_perfis(self):
        perfis = buscar_todos_perfis()
        self.renderizar_grade_perfis(perfis)

    def renderizar_grade_perfis(self, perfis):
        controls = [
            self._criar_card_base(
                conteudo_box=ft.Text(
                    p.nome[0].upper() if p.nome else "?",
                    size=45,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                rotulo=p.nome,
                cor_bg=CORES_AVATAR[idx % len(CORES_AVATAR)],
                on_click=lambda e, p_id=p.id: self.on_selecionar(p_id),
            )
            for idx, p in enumerate(perfis)
        ]

        # Card de Adicionar
        controls.append(
            self._criar_card_base(
                conteudo_box=ft.Icon("add", size=50, color=ft.Colors.GREY_400),
                rotulo="Adicionar Perfil",
                cor_bg=None,
                border_padrao=ft.Border.all(2, ft.Colors.GREY_600),
                on_click=lambda e: abrir_dialogo(self.page_ref, self.dlg_criar_perfil),
            )
        )

        self.row_perfis.controls = controls

    def _criar_card_base(
        self, conteudo_box, rotulo, cor_bg, on_click, border_padrao=None
    ):
        """Helper genérico para evitar repetição no visual dos cards e no evento de hover."""
        b_padrao = border_padrao or ft.Border.all(2, ft.Colors.TRANSPARENT)

        box = ft.Container(
            content=ft.Column(
                [conteudo_box],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=110,
            height=110,
            bgcolor=cor_bg,
            border_radius=12,
            border=b_padrao,
        )
        txt = ft.Text(rotulo, size=15 if cor_bg is None else 16, color=ft.Colors.GREY_400)

        def hover(e):
            is_hover = e.data == "true"
            box.border = ft.Border.all(3, ft.Colors.WHITE) if is_hover else b_padrao
            txt.color = ft.Colors.WHITE if is_hover else ft.Colors.GREY_400

            # Caso o conteúdo do box seja um ícone (Card Adicionar), muda a cor dele também
            if isinstance(conteudo_box, ft.Icon):
                conteudo_box.color = ft.Colors.WHITE if is_hover else ft.Colors.GREY_400

            card.update()

        card = ft.Container(
            content=ft.Column(
                [box, txt],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            on_click=on_click,
            on_hover=hover,
            padding=5,
            border_radius=12,
        )

        return card

    def salvar_perfil(self, e):
        nome = self.txt_novo_nome_perfil.value.strip()
        if not nome:
            mostrar_mensagem(self.page_ref, "Digite um nome!")
            return

        sucesso, msg = criar_novo_perfil(nome)
        mostrar_mensagem(self.page_ref, msg)
        if sucesso:
            fechar_dialogo(self.page_ref, self.dlg_criar_perfil)
            self.txt_novo_nome_perfil.value = ""
            self.carregar_perfis()
            self.page_ref.update()