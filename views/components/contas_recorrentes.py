from datetime import date
import flet as ft
import flet_charts as fch

from database.crud import (
    alternar_pagamento_conta,
    obter_contas_do_mes,
    remover_conta_recorrente,
    salvar_conta_recorrente,
)
from utils.ui_helpers import mostrar_mensagem


class GraficoRendaComprometida(ft.Container):
    """Gráfico que exibe quanto da renda do período está comprometido com contas."""

    def __init__(self, formatar_moeda_func):
        super().__init__(
            padding=15,
            height=290,
            border=ft.Border.all(1, ft.Colors.WHITE_24),
            border_radius=10,
            expand=True,
        )
        self.formatar = formatar_moeda_func

        self.txt_resumo = ft.Text(
            "0,0% comprometido",
            size=12,
            color=ft.Colors.GREY_400,
        )
        self.chart = fch.PieChart(
            sections=[],
            sections_space=2,
            center_space_radius=40,
        )

        self.content = ft.Column(
            [
                ft.Text("Contas Fixas", size=15, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=self.chart,
                    width=300,
                    height=195,
                    alignment=ft.Alignment(0, 0),
                ),
                self.txt_resumo,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.atualizar(None)

    def atualizar(self, comprometimento):
        comprometido = 0.0
        renda = 0.0
        percentual = 0.0

        if isinstance(comprometimento, dict):
            valor_comp = comprometimento.get("total_contas")
            if valor_comp is None:
                valor_comp = comprometimento.get("comprometido", 0.0)
            comprometido = float(valor_comp or 0.0)
            renda = float(comprometimento.get("renda", 0.0) or 0.0)
            if renda > 0:
                percentual = (comprometido / renda) * 100.0
            elif comprometimento.get("percentual") is not None:
                percentual = float(comprometimento.get("percentual") or 0.0)

        restante = max(renda - comprometido, 0.0)
        total = comprometido + restante

        if total > 0:
            self.chart.sections = [
                fch.PieChartSection(
                    value=comprometido or 0.001,
                    title=f"Contas\n{(comprometido / total) * 100:.1f}%",
                    color=ft.Colors.AMBER_400,
                    radius=55,
                    title_style=ft.TextStyle(
                        size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                    ),
                ),
                fch.PieChartSection(
                    value=restante or 0.001,
                    title=f"Livre\n{(restante / total) * 100:.1f}%",
                    color=ft.Colors.TEAL_400,
                    radius=55,
                    title_style=ft.TextStyle(
                        size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                    ),
                ),
            ]
        else:
            self.chart.sections = [
                fch.PieChartSection(
                    value=1.0,
                    title="Sem dados",
                    color=ft.Colors.GREY_700,
                    radius=55,
                    title_style=ft.TextStyle(size=11, color=ft.Colors.WHITE),
                )
            ]

        if renda > 0:
            self.txt_resumo.value = (
                f"{percentual:.1f}% ({self.formatar(comprometido)} de {self.formatar(renda)})"
            )
        else:
            self.txt_resumo.value = f"{percentual:.1f}% ({self.formatar(comprometido)})"


class AbaContasRecorrentes(ft.Container):
    """Aba dedicada às contas recorrentes mensais."""

    def __init__(
        self,
        page_ref,
        perfil_ativo_id,
        obter_periodo,
        on_atualizar,
        formatar_moeda_func,
    ):
        super().__init__(padding=10, visible=False, expand=True)
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.obter_periodo = obter_periodo
        self.on_atualizar = on_atualizar
        self.formatar = formatar_moeda_func
        self.editando_conta_id = None

        self._construir_ui()

    def _construir_ui(self):
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

        self.txt_dia = ft.TextField(
            label="Dia",
            value=f"{date.today().day:02d}",
            width=75,
            hint_text="DD",
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.txt_descricao = ft.TextField(
            label="Descrição",
            width=240,
            hint_text="Ex: Internet, energia, aluguel...",
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.txt_valor = ft.TextField(
            label="Valor",
            width=130,
            hint_text="0,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.dd_forma_pagto = ft.Dropdown(
            label="Pagamento",
            width=150,
            value="Pix",
            options=[
                ft.dropdown.Option("Pix"),
                ft.dropdown.Option("Débito"),
                ft.dropdown.Option("Dinheiro"),
                ft.dropdown.Option("Boleto"),
                ft.dropdown.Option("Transferência"),
            ],
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.txt_parcelas = ft.TextField(
            label="Parcelas",
            width=95,
            hint_text="Opcional",
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=ft.Padding(left=12, right=12, top=12, bottom=12),
        )
        self.btn_salvar = ft.FilledButton(
            "Salvar",
            icon=ft.Icons.SAVE,
            height=48,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar,
        )

        self.painel_formulario = ft.Column(
            [
                ft.Row([self.btn_fechar], alignment=ft.MainAxisAlignment.END),
                ft.Row(
                    [
                        self.txt_dia,
                        self.txt_descricao,
                        self.txt_valor,
                        self.dd_forma_pagto,
                        self.txt_parcelas,
                        self.btn_salvar,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
            ],
            spacing=6,
            visible=False,
        )

        self.tabela = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(c))
                for c in ["Dia", "Descrição", "Pagamento", "Valor", "Pago", "Ações"]
            ],
            rows=[],
        )

        self.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Contas Recorrentes", size=18, weight=ft.FontWeight.BOLD),
                        self.btn_adicionar,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.painel_formulario,
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

    def _limpar_formulario(self):
        self.editando_conta_id = None
        self.txt_dia.value = f"{date.today().day:02d}"
        self.txt_descricao.value = ""
        self.txt_valor.value = ""
        self.dd_forma_pagto.value = "Pix"
        self.txt_parcelas.value = ""
        self.btn_salvar.text = "Salvar"

    def abrir_formulario(self, e=None):
        self._limpar_formulario()
        self.painel_formulario.visible = True
        self.btn_adicionar.visible = False
        if self.page_ref:
            self.page_ref.update()

    def fechar_formulario(self, e=None):
        self._limpar_formulario()
        self.painel_formulario.visible = False
        self.btn_adicionar.visible = True
        if self.page_ref:
            self.page_ref.update()

    def _iniciar_edicao(self, conta: dict):
        self.editando_conta_id = conta.get("id")
        dia = conta.get("dia_vencimento", date.today().day)
        self.txt_dia.value = f"{int(dia):02d}" if str(dia).isdigit() else f"{date.today().day:02d}"
        self.txt_descricao.value = conta.get("descricao", "")

        valor_atual = float(conta.get("valor", 0.0) or 0.0)
        self.txt_valor.value = f"{valor_atual:.2f}".replace(".", ",")

        forma = conta.get("forma_pagamento") or "Pix"
        opcoes_validas = [opt.key for opt in (self.dd_forma_pagto.options or [])]
        self.dd_forma_pagto.value = forma if forma in opcoes_validas else "Pix"

        tot_parc = conta.get("total_parcelas")
        self.txt_parcelas.value = str(tot_parc) if tot_parc else ""
        self.btn_salvar.text = "Atualizar"

        self.painel_formulario.visible = True
        self.btn_adicionar.visible = False
        if self.page_ref:
            self.page_ref.update()

    def salvar(self, e=None):
        if not self.perfil_ativo_id[0]:
            mostrar_mensagem(self.page_ref, "❌ Selecione um perfil primeiro!")
            return

        try:
            dia = int((self.txt_dia.value or "").strip())
            if not (1 <= dia <= 31):
                mostrar_mensagem(self.page_ref, "❌ Informe um dia válido entre 1 e 31!")
                return

            val_str = (
                str(self.txt_valor.value or "")
                .replace("R$", "")
                .replace(" ", "")
                .replace(",", ".")
                .strip()
            )
            val = float(val_str)
            desc = (self.txt_descricao.value or "").strip()
            forma = self.dd_forma_pagto.value or "Pix"

            parcelas_str = (self.txt_parcelas.value or "").strip()
            total_parcelas = int(parcelas_str) if parcelas_str else None

            if not desc or val <= 0:
                mostrar_mensagem(self.page_ref, "❌ Preencha descrição e um valor maior que zero!")
                return

            mes_sel, ano_sel = self.obter_periodo()
            eh_edicao = self.editando_conta_id is not None

            salvar_conta_recorrente(
                descricao=desc,
                valor=val,
                dia_vencimento=dia,
                forma_pagamento=forma,
                perfil_id=self.perfil_ativo_id[0],
                mes_inicio=mes_sel,
                ano_inicio=ano_sel,
                conta_id=self.editando_conta_id,
                total_parcelas=total_parcelas,
                reajuste=eh_edicao,
            )

            self._limpar_formulario()
            self.painel_formulario.visible = False
            self.btn_adicionar.visible = True

            msg = "✅ Conta recorrente atualizada com sucesso!" if eh_edicao else "✅ Conta recorrente salva com sucesso!"
            mostrar_mensagem(self.page_ref, msg)
            self.on_atualizar()
        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao salvar conta recorrente: {ex}")

    def _alternar_pago(self, conta_id, pago):
        mes_sel, ano_sel = self.obter_periodo()
        alternar_pagamento_conta(conta_id, mes_sel, ano_sel, pago)
        self.on_atualizar()

    def _excluir(self, conta_id):
        if remover_conta_recorrente(conta_id):
            if self.editando_conta_id == conta_id:
                self._limpar_formulario()
                self.painel_formulario.visible = False
                self.btn_adicionar.visible = True
            mostrar_mensagem(self.page_ref, "✅ Conta recorrente removida!")
            self.on_atualizar()

    def atualizar(self, dados: dict):
        if not self.perfil_ativo_id[0]:
            self.tabela.rows = []
            return

        mes_sel, ano_sel = self.obter_periodo()
        contas = dados.get("contas_recorrentes")
        if contas is None:
            contas = obter_contas_do_mes(self.perfil_ativo_id[0], mes_sel, ano_sel)

        novas_linhas = []
        for conta in contas or []:
            if isinstance(conta, dict):
                conta_dict = conta
                conta_id = conta.get("id")
                dia = conta.get("dia_vencimento", "-")
                descricao_base = conta.get("descricao", "")
                num_parc = conta.get("numero_parcela")
                tot_parc = conta.get("total_parcelas")
                descricao = (
                    f"{descricao_base} ({num_parc}/{tot_parc})"
                    if (num_parc and tot_parc)
                    else descricao_base
                )
                forma = conta.get("forma_pagamento") or "-"
                valor = float(conta.get("valor_efetivo", conta.get("valor", 0.0)) or 0.0)
                pago = bool(conta.get("pago", False))
            else:
                conta_id = getattr(conta, "id", None)
                dia = getattr(conta, "dia_vencimento", "-")
                descricao = getattr(conta, "descricao", "")
                forma = getattr(conta, "forma_pagamento", "-") or "-"
                valor = float(getattr(conta, "valor", 0.0) or 0.0)
                pago = bool(getattr(conta, "pago", False))
                conta_dict = {
                    "id": conta_id,
                    "dia_vencimento": dia,
                    "descricao": descricao,
                    "forma_pagamento": forma,
                    "valor": valor,
                    "total_parcelas": getattr(conta, "total_parcelas", None),
                }

            novas_linhas.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(f"{int(dia):02d}" if str(dia).isdigit() else str(dia))
                        ),
                        ft.DataCell(ft.Text(descricao)),
                        ft.DataCell(ft.Text(forma)),
                        ft.DataCell(ft.Text(self.formatar(valor))),
                        ft.DataCell(
                            ft.Switch(
                                value=pago,
                                on_change=lambda e, cid=conta_id: self._alternar_pago(
                                    cid, bool(e.control.value)
                                ),
                            )
                        ),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        tooltip="Editar valor/conta",
                                        icon_color=ft.Colors.BLUE_400,
                                        on_click=lambda e, c=conta_dict: self._iniciar_edicao(c),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        tooltip="Excluir",
                                        icon_color=ft.Colors.RED_400,
                                        on_click=lambda e, cid=conta_id: self._excluir(cid),
                                    ),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )

        self.tabela.rows = novas_linhas