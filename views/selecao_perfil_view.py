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

        self.row_perfis = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER, spacing=30, wrap=True
        )
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
                    on_click=lambda e: fechar_dialogo(
                        self.page_ref, self.dlg_criar_perfil
                    ),
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
        self.row_perfis.controls.clear()
        for idx, p in enumerate(perfis):
            self.row_perfis.controls.append(
                self.criar_card_perfil(p, CORES_AVATAR[idx % len(CORES_AVATAR)])
            )
        self.row_perfis.controls.append(self.criar_card_adicionar())

    def criar_card_perfil(self, perfil, cor_bg):
        letra = perfil.nome[0].upper() if perfil.nome else "?"
        box = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        letra,
                        size=45,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=110,
            height=110,
            bgcolor=cor_bg,
            border_radius=12,
            border=ft.Border.all(2, ft.Colors.TRANSPARENT),
        )
        txt = ft.Text(
            perfil.nome,
            size=16,
            color=ft.Colors.GREY_400,
            weight=ft.FontWeight.W_500,
        )
        card = ft.Container(
            content=ft.Column(
                [box, txt],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            on_click=lambda e, p_id=perfil.id: self.on_selecionar(p_id),
            padding=5,
            border_radius=12,
        )

        def hover(e):
            box.border = (
                ft.Border.all(3, ft.Colors.WHITE)
                if e.data == "true"
                else ft.Border.all(2, ft.Colors.TRANSPARENT)
            )
            txt.color = ft.Colors.WHITE if e.data == "true" else ft.Colors.GREY_400
            card.update()

        card.on_hover = hover
        return card

    def criar_card_adicionar(self):
        box = ft.Container(
            content=ft.Column(
                [ft.Icon(ft.Icons.ADD, size=50, color=ft.Colors.GREY_400)],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=110,
            height=110,
            border_radius=12,
            border=ft.Border.all(2, ft.Colors.GREY_600),
        )
        txt = ft.Text("Adicionar Perfil", size=15, color=ft.Colors.GREY_400)
        card = ft.Container(
            content=ft.Column(
                [box, txt],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            on_click=lambda e: abrir_dialogo(self.page_ref, self.dlg_criar_perfil),
            padding=5,
            border_radius=12,
        )

        def hover(e):
            box.border = (
                ft.Border.all(3, ft.Colors.WHITE)
                if e.data == "true"
                else ft.Border.all(2, ft.Colors.GREY_600)
            )
            box.content.controls[0].color = (
                ft.Colors.WHITE if e.data == "true" else ft.Colors.GREY_400
            )
            txt.color = ft.Colors.WHITE if e.data == "true" else ft.Colors.GREY_400
            card.update()

        card.on_hover = hover
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