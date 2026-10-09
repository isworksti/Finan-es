from datetime import date
import flet as ft
from database.crud import MESES, atualizar_transacao, buscar_cartoes_do_perfil, eh_credito
from utils.date_utils import extrair_data
from utils.ui_helpers import mostrar_mensagem

class EditarTransacaoDialog(ft.AlertDialog):
    def __init__(self, page_ref: ft.Page, perfil_ativo_id, on_sucesso):
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.on_sucesso = on_sucesso
        self.transacao_em_edicao_id = None

        self.txt_data = ft.TextField(label="Dia", width=65, hint_text="DD")
        self.txt_descricao = ft.TextField(label="Descrição", expand=True)
        self.txt_valor = ft.TextField(label="Valor (R$)", width=110, keyboard_type=ft.KeyboardType.NUMBER)

        opts_meses = [ft.dropdown.Option(str(k), text=str(v)) for k, v in MESES]
        self.dropdown_mes = ft.Dropdown(label="Mês da Fatura", options=opts_meses, width=150)
        
        opts_anos = [ft.dropdown.Option(str(y)) for y in range(2024, 2028)]
        self.dropdown_ano = ft.Dropdown(label="Ano", options=opts_anos, width=110)

        opts_tipos = [ft.dropdown.Option("Entrada"), ft.dropdown.Option("Saída")]
        self.dropdown_tipo = ft.Dropdown(label="Tipo", options=opts_tipos, width=115)

        opts_pagto = [ft.dropdown.Option(p) for p in ["Dinheiro", "PIX", "Crédito", "Débito"]]
        self.dropdown_pagamento = ft.Dropdown(label="Pagamento", options=opts_pagto, width=120, on_select=self.ao_mudar_forma_pagamento)

        self.dropdown_cartao = ft.Dropdown(label="Cartão", options=[], width=140, disabled=True)

        super().__init__(
            title=ft.Text("Editar Lançamento"),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Row([self.txt_data, self.dropdown_mes, self.dropdown_ano], spacing=10),
                        ft.Row([self.txt_descricao]),
                        ft.Row([self.txt_valor, self.dropdown_tipo], spacing=10),
                        ft.Row([self.dropdown_pagamento, self.dropdown_cartao], spacing=10),
                    ],
                    tight=True,
                    spacing=12,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.fechar()),
                ft.FilledButton("Salvar", bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=self.salvar_edicao),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def carregar_cartoes(self):
        if not self.perfil_ativo_id[0]:
            return
        cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        self.dropdown_cartao.options = [ft.dropdown.Option(key=str(c.id), text=c.nome) for c in cartoes]

    def ao_mudar_forma_pagamento(self, e=None):
        is_credito = eh_credito(self.dropdown_pagamento.value)
        self.dropdown_cartao.disabled = not is_credito
        if not is_credito:
            self.dropdown_cartao.value = None
        if self.page:
            self.dropdown_cartao.update()

    def abrir_para_edicao(self, transacao):
        self.transacao_em_edicao_id = transacao.id
        self.carregar_cartoes()

        t_data = extrair_data(transacao) or date.today()

        self.txt_data.value = f"{t_data.day:02d}"
        self.dropdown_mes.value = str(t_data.month)
        self.dropdown_ano.value = str(t_data.year)
        self.txt_descricao.value = transacao.descricao or ""
        self.txt_valor.value = f"{transacao.valor:.2f}".replace(".", ",")
        self.dropdown_tipo.value = transacao.tipo
        self.dropdown_pagamento.value = transacao.forma_pagamento or "PIX"
        self.dropdown_cartao.value = str(transacao.cartao_id) if transacao.cartao_id else None

        self.ao_mudar_forma_pagamento()

        self.open = True
        if self.page:
            self.page.update()

    def fechar(self):
        self.transacao_em_edicao_id = None
        self.open = False
        if self.page:
            self.page.update()

    def salvar_edicao(self, e):
        if not self.transacao_em_edicao_id:
            return

        try:
            mes = int(self.dropdown_mes.value)
            ano = int(self.dropdown_ano.value)
            dia = int(self.txt_data.value.strip())
            dt = date(ano, mes, dia)

            val = float(self.txt_valor.value.replace("R$", "").replace(" ", "").replace(",", ".").strip())
            desc = self.txt_descricao.value.strip()

            if not desc:
                raise ValueError("Descrição vazia")

            cartao_id = int(self.dropdown_cartao.value) if (eh_credito(self.dropdown_pagamento.value) and self.dropdown_cartao.value) else None

            atualizar_transacao(
                transacao_id=self.transacao_em_edicao_id,
                descricao=desc,
                valor=val,
                tipo=self.dropdown_tipo.value,
                forma_pagamento=self.dropdown_pagamento.value,
                data_dt=dt,
                cartao_id=cartao_id,
            )

            self.fechar()
            mostrar_mensagem(self.page_ref, "✅ Lançamento atualizado com sucesso!")
            self.on_sucesso()

        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao salvar edição: {ex}")