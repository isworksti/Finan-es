import flet as ft
from ofxparse import OfxParser
from database.crud import importar_transacoes_ofx
from utils.ui_helpers import mostrar_mensagem

class ImportacaoView(ft.Column):
    def __init__(self, page: ft.Page, perfil_id: int):
        super().__init__(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            spacing=20,
        )
        self.page_ref = page
        self.perfil_id = perfil_id

        # Configurar o seletor de ficheiros nativo do Flet
        self.file_picker = ft.FilePicker(on_result=self.processar_ficheiro_ofx)
        self.page_ref.overlay.append(self.file_picker)

        self.controls = [
            ft.Text("Importar Extrato Bancário (OFX)", size=28, weight=ft.FontWeight.BOLD),
            ft.Text("Selecione o ficheiro OFX descarregado do seu banco para importar as transações.", color=ft.Colors.GREY_400),
            ft.Container(height=10),
            ft.FilledButton(
                "Selecionar Ficheiro OFX",
                icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                on_click=lambda _: self.file_picker.pick_files(
                    allow_multiple=False,
                    allowed_extensions=["ofx"]
                ),
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_700,
                    padding=20,
                )
            )
        ]

    def processar_ficheiro_ofx(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return  # O utilizador cancelou a seleção

        file_path = e.files[0].path

        try:
            # Ler o ficheiro OFX com codificação robusta para caracteres bancários
            with open(file_path, "r", encoding="latin-1") as fileobj:
                ofx = OfxParser.parse(fileobj)

            transacoes_extraidas = []
            
            # Acede à conta e respetivo extrato
            statement = ofx.account.statement
            for t in statement.transactions:
                transacoes_extraidas.append({
                    "data": t.date.date() if hasattr(t.date, "date") else t.date,
                    "valor": float(t.amount),
                    "descricao": t.memo or t.payee or "Transação bancária"
                })

            if not transacoes_extraidas:
                mostrar_mensagem(self.page_ref, "⚠️ Nenhuma transação encontrada no ficheiro.")
                return

            # Gravar na base de dados através do CRUD
            importadas, duplicadas = importar_transacoes_ofx(self.perfil_id, transacoes_extraidas)
            
            msg = f"✅ Sucesso! {importadas} transações importadas."
            if duplicadas > 0:
                msg += f" ({duplicadas} duplicadas ignoradas)."
                
            mostrar_mensagem(self.page_ref, msg)

        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao ler ficheiro OFX: {ex}")