import flet as ft

def abrir_dialogo(page: ft.Page, dlg: ft.AlertDialog):
    page.dialog = dlg
    dlg.open = True
    page.update()

def fechar_dialogo(page: ft.Page, dlg: ft.AlertDialog):
    dlg.open = False
    page.update()

def mostrar_mensagem(page: ft.Page, texto: str):
    """Mostra um aviso (SnackBar) na parte de baixo da tela.

    Flet 0.80+ exige page.show_dialog(); o padrão antigo (page.snack_bar)
    não exibe nada. Se a mensagem falhar por qualquer motivo, ela só vai
    para o terminal: um aviso nunca pode impedir a ação principal.
    """
    try:
        snack = ft.SnackBar(content=ft.Text(texto))
        if hasattr(page, "show_dialog"):
            page.show_dialog(snack)
        else:  # Flet antigo (< 0.80)
            page.snack_bar = snack
            page.snack_bar.open = True
            page.update()
    except Exception as ex:
        print(f"[aviso] não foi possível exibir a mensagem {texto!r}: {ex}")