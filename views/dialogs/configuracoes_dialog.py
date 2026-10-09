import flet as ft

class ConfiguracoesDialog(ft.AlertDialog):
    def __init__(self, on_abrir_gestao_cartoes):
        self.on_abrir_gestao_cartoes = on_abrir_gestao_cartoes

        super().__init__(
            title=ft.Row([ft.Icon(ft.Icons.SETTINGS, size=24), ft.Text("Configurações do Sistema")]),
            content=ft.Container(
                width=350,
                content=ft.Column(
                    [
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.CREDIT_CARD, color=ft.Colors.BLUE_400),
                            title=ft.Text("Gerenciamento de Cartões"),
                            subtitle=ft.Text("Adicionar, editar e remover cartões"),
                            on_click=lambda e: self.on_abrir_gestao_cartoes(),
                        ),
                        ft.Divider(),
                    ],
                    tight=True,
                    spacing=5,
                ),
            ),
            actions=[
                ft.TextButton("Fechar", on_click=lambda e: self.fechar())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def fechar(self):
        self.open = False
        if self.page:
            self.page.update()