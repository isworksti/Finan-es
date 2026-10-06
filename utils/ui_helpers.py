import flet as ft

def abrir_dialogo(page: ft.Page, dlg: ft.AlertDialog):
    page.dialog = dlg
    dlg.open = True
    page.update()

def fechar_dialogo(page: ft.Page, dlg: ft.AlertDialog):
    dlg.open = False
    page.update()

def mostrar_mensagem(page: ft.Page, texto: str):
    page.snack_bar = ft.SnackBar(content=ft.Text(texto))
    page.snack_bar.open = True
    page.update()