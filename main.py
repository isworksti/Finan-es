import flet as ft
from database.connection import Base, engine
from database.migracoes import aplicar_migracoes
import database.models  # noqa: F401  (registra todas as tabelas, inclusive faturas_mensais)
from views.dashboard_view import DashboardView
from views.selecao_perfil_view import SelecaoPerfilView

Base.metadata.create_all(bind=engine)
aplicar_migracoes(engine)  # acrescenta colunas novas em bancos antigos, sem perder dados

def main(page: ft.Page):
    page.title = "Controle Financeiro Pessoal"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1280
    page.window.height = 760
    page.window.min_width = 960
    page.window.min_height = 600


    perfil_ativo_id = [None]

    def trocar_perfil(novo_id: int):
        perfil_ativo_id[0] = novo_id
        selecao_view.visible = False
        dashboard_view.carregar_perfis_header()
        dashboard_view.carregar_dados()
        dashboard_view.visible = True
        page.update()

    def ir_para_selecao_perfil():
        dashboard_view.visible = False
        selecao_view.carregar_perfis()
        selecao_view.visible = True
        page.update()

    selecao_view = SelecaoPerfilView(page=page, on_selecionar=trocar_perfil)
    dashboard_view = DashboardView(
        page=page,
        perfil_ativo_id=perfil_ativo_id,
        on_trocar_perfil=ir_para_selecao_perfil,
    )

    page.add(selecao_view, dashboard_view)
    selecao_view.carregar_perfis()

ft.run(main)