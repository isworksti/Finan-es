from datetime import date
import flet as ft
import time

from database.crud import (
    remover_transacao,
    salvar_transacao,
    alternar_status_pagamento,
    buscar_cartoes_do_perfil,
)
from views.components.tabelas_transacoes import gerar_linhas_tabela
from utils.ui_helpers import mostrar_mensagem


class AbaLancamentosGerais(ft.Container):
    """Aba dedicada aos lançamentos gerais (entradas e saídas)."""

    def __init__(
        self,
        page_ref,
        perfil_ativo_id,
        obter_periodo,
        on_atualizar,
        formatar_moeda_func,
        extrair_data_func,
        on_editar_transacao,
    ):
        super().__init__(padding=10, visible=True, expand=True)
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.obter_periodo = obter_periodo
        self.on_atualizar = on_atualizar
        self.formatar = formatar_moeda_func
        self.extrair_data = extrair_data_func
        self.on_editar_transacao = on_editar_transacao
        self._handler_teclado_anterior = None

        self._construir_ui()

    def _construir_ui(self):
        self.campo_busca = ft.TextField(
            label="Buscar",
            hint_text="Descrição...",
            text_size=12,
            height=40,
            expand=True,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            on_change=lambda e: self.on_atualizar(),
        )
        self.dropdown_forma = ft.Dropdown(
            label="Pagamento",
            text_size=12,
            height=40,
            width=165,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            options=[
                ft.dropdown.Option(o)
                for o in ["Todas", "Débito", "PIX", "Dinheiro", "Crédito"]
            ],
            value="Todas",
            on_select=lambda e: self.on_atualizar(),
        )
        barra_filtros = ft.Row([self.campo_busca, self.dropdown_forma], spacing=10)

        self.btn_adicionar = ft.FilledButton(
            "Adicionar",
            icon=ft.Icons.ADD,
            height=40,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.abrir_formulario,
        )
        self.btn_fechar = ft.IconButton(
            icon=ft.Icons.CLOSE,
            tooltip="Fechar formulário",
            on_click=self.fechar_formulario,
        )

        self.txt_data = ft.TextField(
            label="Dia",
            value=f"{date.today().day:02d}",
            width=68,
            hint_text="DD",
            text_size=12,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=10, right=10, top=10, bottom=10),
        )
        self.txt_descricao = ft.TextField(
            label="Descrição",
            width=195,
            hint_text="Ex: Mercado, aluguel...",
            text_size=12,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=10, right=10, top=10, bottom=10),
        )
        self.txt_valor = ft.TextField(
            label="Valor",
            width=115,
            hint_text="0,00",
            text_size=12,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=10, right=10, top=10, bottom=10),
        )
        self.dropdown_tipo = ft.Dropdown(
            label="Tipo",
            width=115,
            text_size=12,
            value="Saída",
            options=[ft.dropdown.Option(o) for o in ["Entrada", "Saída"]],
            on_select=self._ao_mudar_tipo,
            content_padding=ft.Padding(left=10, right=10, top=10, bottom=10),
        )
        self.chk_pago = ft.Checkbox(label="Pago", value=True, visible=True)
        self.dropdown_pagamento = ft.Dropdown(
            label="Pagamento",
            width=135,
            text_size=12,
            value="PIX",
            options=[
                ft.dropdown.Option(o)
                for o in ["Dinheiro", "PIX", "Débito", "Crédito"]
            ],
            content_padding=ft.Padding(left=10, right=10, top=10, bottom=10),
        )
        self.btn_salvar = ft.FilledButton(
            "Salvar",
            icon=ft.Icons.SAVE,
            height=42,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar,
        )

        linha_campos = ft.Row(
            [
                self.txt_data,
                self.txt_descricao,
                self.txt_valor,
                self.dropdown_tipo,
                self.chk_pago,
                self.dropdown_pagamento,
                self.btn_salvar,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=False,
            scroll=ft.ScrollMode.AUTO,
        )

        self.painel_formulario = ft.Column(
            [
                ft.Row([self.btn_fechar], alignment=ft.MainAxisAlignment.END),
                linha_campos,
            ],
            spacing=6,
            visible=False,
        )

        self.tabela = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(c))
                for c in ["Data", "Descrição", "Tipo", "Pago?", "Pagamento", "Valor", "Ações"]
            ],
            rows=[],
        )

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Histórico de Lançamentos", size=18, weight=ft.FontWeight.BOLD),
                        self.btn_adicionar,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.painel_formulario,
                barra_filtros,
                ft.Column(
                    [ft.Row([self.tabela], scroll=ft.ScrollMode.AUTO)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
            expand=True,
        )

    def _ao_tecla_pressionada(self, e: ft.KeyboardEvent):
        if not self.painel_formulario.visible:
            return
        if e.key == "Enter":
            self.salvar(e)
        elif e.key == "Escape":
            self.fechar_formulario(e)

    def _ativar_atalhos_teclado(self):
        if self.page_ref and self.page_ref.on_keyboard_event != self._ao_tecla_pressionada:
            self._handler_teclado_anterior = self.page_ref.on_keyboard_event
            self.page_ref.on_keyboard_event = self._ao_tecla_pressionada

    def _restaurar_atalhos_teclado(self):
        if self.page_ref and self.page_ref.on_keyboard_event == self._ao_tecla_pressionada:
            self.page_ref.on_keyboard_event = self._handler_teclado_anterior
            self._handler_teclado_anterior = None

    def obter_filtros(self):
        busca = (self.campo_busca.value or "").strip().lower()
        forma = self.dropdown_forma.value or "Todas"
        return busca, forma

    async def abrir_formulario(self, e=None):
        self.painel_formulario.visible = True
        self.btn_adicionar.visible = False
        self._ativar_atalhos_teclado()
        if self.page_ref:
            self.page_ref.update()
            await self.txt_data.focus()

    def fechar_formulario(self, e=None):
        self.painel_formulario.visible = False
        self.btn_adicionar.visible = True
        self._restaurar_atalhos_teclado()
        if self.page_ref:
            self.page_ref.update()

    def _ao_mudar_tipo(self, e=None):
        eh_saida = self.dropdown_tipo.value == "Saída"
        self.chk_pago.visible = eh_saida
        if not eh_saida:
            self.chk_pago.value = True
        if self.page_ref:
            self.page_ref.update()

    def _parse_valor_moeda(self, raw_valor: str) -> float:
        limpo = (
            str(raw_valor or "")
            .replace("R$", "")
            .replace("r$", "")
            .replace(" ", "")
            .strip()
        )
        if not limpo:
            raise ValueError("VALOR_VAZIO")

        if "," in limpo:
            # Ex: "1.250,50" -> "1250.50" ou "289,41" -> "289.41"
            limpo = limpo.replace(".", "").replace(",", ".")

        return float(limpo)

    def salvar(self, e=None):
        agora = time.monotonic()
        if agora - getattr(self, "_ultimo_salvar_em", 0.0) < 0.25:
            return
        self._ultimo_salvar_em = agora

        try:
            if not self.perfil_ativo_id[0]:
                mostrar_mensagem(self.page_ref, "❌ Selecione um perfil primeiro!")
                return

            mes, ano = self.obter_periodo()
            dia_str = (self.txt_data.value or "").strip()
            if not dia_str.isdigit():
                mostrar_mensagem(self.page_ref, "❌ Informe um dia válido!")
                return

            dia = int(dia_str)
            dt = date(ano, mes, dia)

            desc = (self.txt_descricao.value or "").strip()
            try:
                val = self._parse_valor_moeda(self.txt_valor.value)
            except ValueError:
                mostrar_mensagem(self.page_ref, "❌ Preencha descrição e um valor maior que zero!")
                return

            if not desc or val <= 0:
                mostrar_mensagem(self.page_ref, "❌ Preencha descrição e um valor maior que zero!")
                return

            forma_pgto = self.dropdown_pagamento.value or "PIX"
            cartao_id = None
            if forma_pgto == "Crédito":
                cartoes = buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
                if cartoes:
                    cartao_id = cartoes[0].id

            salvar_transacao(
                descricao=desc,
                valor=val,
                tipo=self.dropdown_tipo.value or "Saída",
                forma_pagamento=forma_pgto,
                data_dt=dt,
                perfil_id=self.perfil_ativo_id[0],
                cartao_id=cartao_id,
            )

            self.txt_descricao.value = ""
            self.txt_valor.value = ""

            mostrar_mensagem(self.page_ref, "✅ Lançamento adicionado com sucesso!")
            self.on_atualizar()
            if self.page_ref:
                self.page_ref.run_task(self.txt_descricao.focus)
        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao adicionar lançamento: {ex}")
        finally:
            self._salvando = False

    def _ao_mudar_pago(self, transacao_id, novo_status):
        alternar_status_pagamento(transacao_id, novo_status)
        self.on_atualizar()

    def _excluir(self, transacao_id):
        if remover_transacao(transacao_id):
            mostrar_mensagem(self.page_ref, "✅ Transação removida!")
            self.on_atualizar()

    def _chave_transacao(self, t):
        t_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
        if t_id is not None:
            return ("id", t_id)

        if isinstance(t, dict):
            return (
                "fallback",
                t.get("data"),
                t.get("descricao"),
                t.get("tipo"),
                t.get("forma_pagamento"),
                t.get("valor"),
            )
        return (
            "fallback",
            getattr(t, "data", None),
            getattr(t, "descricao", None),
            getattr(t, "tipo", None),
            getattr(t, "forma_pagamento", None),
            getattr(t, "valor", None),
        )

    def atualizar(self, dados: dict):
        self.tabela.rows = []
        if not dados:
            return

        vistas = set()
        transacoes_unicas = []
        for t in dados.get("transacoes_mes", []) or []:
            chave = self._chave_transacao(t)
            if chave not in vistas:
                vistas.add(chave)
                transacoes_unicas.append(t)

        self.tabela.rows = gerar_linhas_tabela(
            transacoes_unicas,
            self.on_editar_transacao,
            self._excluir,
            self.extrair_data,
            self.formatar,
            modo_cartao=False,
            on_mudar_status_pago_cb=self._ao_mudar_pago,
        )