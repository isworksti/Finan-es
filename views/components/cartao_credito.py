import flet as ft

from database.crud import (
    MESES,
    atualizar_status_fatura,
    buscar_cartoes_do_perfil,
    buscar_transacoes_cartao_periodo,
    buscar_transacoes_do_perfil,
    calcular_limites_cartao,
    deletar_cartao,
    obter_ou_criar_fatura_mensal,
    remover_transacao,
    salvar_cartao,
)
from services.fatura_service import obter_mes_ano_fatura, projetar_faturas_futuras
from utils.ui_helpers import mostrar_mensagem
from views.components.cartao_card import criar_card_cartao


class AbaCartaoCredito(ft.Container):
    """Aba focada nos cartões de crédito ativos, cadastro rápido e tabela de cartões."""

    def __init__(
        self,
        page_ref,
        perfil_ativo_id,
        obter_periodo,
        on_atualizar,
        formatar_moeda_func,
        extrair_data_func,
        on_editar_transacao,
        on_abrir_gestao_cartoes=None,
    ):
        super().__init__(padding=10, visible=True, expand=True)
        self.page_ref = page_ref
        self.perfil_ativo_id = perfil_ativo_id
        self.obter_periodo = obter_periodo
        self.on_atualizar = on_atualizar
        self.formatar = formatar_moeda_func
        self.extrair_data = extrair_data_func
        self.on_editar_transacao = on_editar_transacao
        self.on_abrir_gestao_cartoes = on_abrir_gestao_cartoes
        self.cartao_editando_id = None
        self.cartao_selecionado_id = None
        self._ultimo_dados = None

        self._construir_ui()

    def _construir_ui(self):
        self.dropdown_forma = ft.Dropdown(
            label="Status / Ciclo",
            text_size=12,
            height=40,
            expand=True,
            content_padding=ft.Padding(left=10, right=10, top=0, bottom=0),
            options=[
                ft.dropdown.Option(o)
                for o in ["Todos", "Com limite livre", "Alto uso (>=70%)"]
            ],
            value="Todos",
            on_select=lambda e: self.atualizar(self._ultimo_dados),
        )
        barra_filtros = ft.Row([self.dropdown_forma], spacing=10)

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

        # Campos do menu "Adicionar" (larguras explícitas para não sobrepor)
        self.txt_nome_cartao = ft.TextField(
            label="Nome do Cartão",
            width=220,
            height=44,
            text_size=12,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        )
        self.txt_limite_cartao = ft.TextField(
            label="Limite (R$)",
            width=150,
            height=44,
            text_size=12,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        )
        self.txt_dia_fechamento = ft.TextField(
            label="Dia Fechamento",
            width=135,
            height=44,
            text_size=12,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        )
        self.txt_dia_vencimento = ft.TextField(
            label="Dia Vencimento",
            width=135,
            height=44,
            text_size=12,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self.salvar,
            content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
        )
        self.btn_salvar = ft.FilledButton(
            "Salvar Cartão",
            icon=ft.Icons.SAVE,
            height=44,
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            on_click=self.salvar,
        )

        self.container_grafico_cartoes = ft.Container(
            content=ft.Column([], tight=True),
            visible=False,
            padding=ft.Padding(top=0, bottom=0, left=6, right=0),
        )

        linha_campos = ft.Row(
            [
                self.txt_nome_cartao,
                self.txt_limite_cartao,
                self.txt_dia_fechamento,
                self.txt_dia_vencimento,
                self.btn_salvar,
            ],
            spacing=10,
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
            column_spacing=10,
            horizontal_margin=8,
            expand=True,
            columns=[
                ft.DataColumn(ft.Text("Cartão", size=12)),
                ft.DataColumn(ft.Text("Limite", size=12), numeric=True),
                ft.DataColumn(ft.Text("Usado", size=12), numeric=True),
                ft.DataColumn(ft.Text("Disponível", size=12), numeric=True),
                ft.DataColumn(ft.Text("Fech.", size=12)),
                ft.DataColumn(ft.Text("Venc.", size=12)),
                ft.DataColumn(ft.Text("Fatura", size=12)),
                ft.DataColumn(ft.Text("Ações", size=12)),
            ],
            rows=[],
        )

        header_cartao = ft.Row(
            [
                ft.Text("Cartões de Crédito", size=18, weight=ft.FontWeight.BOLD),
                self.btn_adicionar,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        tabela_container = ft.Container(
            content=self.tabela,
            expand=True,
        )

        tabela_scroll = ft.Column(
            [ft.Row([tabela_container], expand=True)],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        coluna_esquerda = ft.Column(
            [
                header_cartao,
                self.painel_formulario,
                barra_filtros,
                tabela_scroll,
            ],
            spacing=10,
            expand=True,
        )

        self.content = ft.Row(
            [
                coluna_esquerda,
                self.container_grafico_cartoes,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )

    def _ao_selecionar_cartao(self, cartao):
        if self.cartao_selecionado_id == cartao.id:
            self.cartao_selecionado_id = None
        else:
            self.cartao_selecionado_id = cartao.id
        self.atualizar(self._ultimo_dados)
        page = self._obter_pagina()
        if page:
            page.update()

    def _atualizar_grafico_cartoes(self, cartoes_filtrados, dados: dict = None):
        if not self.perfil_ativo_id[0] or not self.cartao_selecionado_id:
            self.container_grafico_cartoes.visible = False
            self.container_grafico_cartoes.content = ft.Column([], tight=True)
            return

        cartao_alvo = next(
            (c for c in cartoes_filtrados if c.id == self.cartao_selecionado_id),
            None,
        )
        if not cartao_alvo:
            self.cartao_selecionado_id = None
            self.container_grafico_cartoes.visible = False
            self.container_grafico_cartoes.content = ft.Column([], tight=True)
            return

        mes_sel, ano_sel = self.obter_periodo()
        transacoes_todas = (
            dados.get("transacoes_todas")
            if isinstance(dados, dict) and dados.get("transacoes_todas") is not None
            else buscar_transacoes_do_perfil(self.perfil_ativo_id[0])
        )
        mapa_cartoes = (
            dados.get("mapa_cartoes")
            if isinstance(dados, dict) and dados.get("mapa_cartoes") is not None
            else {c.id: c.nome for c in cartoes_filtrados}
        )

        card_ui = criar_card_cartao(
            page_ref=self._obter_pagina(),
            cartao=cartao_alvo,
            mes_sel=mes_sel,
            ano_sel=ano_sel,
            transacoes_todas=transacoes_todas,
            mapa_cartoes=mapa_cartoes,
            on_atualizar_dados=self.on_atualizar,
            formatar_moeda_func=self.formatar,
            mostrar_mensagem_func=mostrar_mensagem,
            obter_ou_criar_fatura_mensal_func=obter_ou_criar_fatura_mensal,
            atualizar_status_fatura_func=atualizar_status_fatura,
            calcular_limites_cartao_func=calcular_limites_cartao,
            projetar_faturas_futuras_func=projetar_faturas_futuras,
            obter_mes_ano_fatura_func=obter_mes_ano_fatura,
            MESES_LISTA=MESES,
        )

        self.container_grafico_cartoes.width = 340
        self.container_grafico_cartoes.visible = True
        self.container_grafico_cartoes.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            f"Detalhes: {cartao_alvo.nome}",
                            weight=ft.FontWeight.BOLD,
                            size=13,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_size=16,
                            tooltip="Fechar gráfico",
                            on_click=lambda e: self._ao_selecionar_cartao(cartao_alvo),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                card_ui,
            ],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        )

    def obter_filtros(self):
        forma = self.dropdown_forma.value or "Todos"
        return "", forma

    def _filtrar_cartoes_ativos(self, cartoes):
        return [
            c
            for c in (cartoes or [])
            if getattr(c, "ativo", True) is not False and not getattr(c, "inativo", False)
        ]

    def abrir_formulario(self, e=None):
        self.cartao_editando_id = None
        self.btn_salvar.text = "Salvar Cartão"
        self.txt_nome_cartao.value = ""
        self.txt_limite_cartao.value = ""
        self.txt_dia_fechamento.value = ""
        self.txt_dia_vencimento.value = ""
        self.painel_formulario.visible = True
        self.btn_adicionar.visible = False
        if self.page_ref:
            self.page_ref.update()
            self.page_ref.run_task(self.txt_nome_cartao.focus)

    def _abrir_dialogo(self, dlg: ft.AlertDialog):
        page = self._obter_pagina()
        if not page:
            return
        if hasattr(page, "show_dialog"):
            page.show_dialog(dlg)
        elif hasattr(page, "open"):
            page.open(dlg)
        else:
            page.dialog = dlg
            dlg.open = True
            page.update()

    def _fechar_dialogo(self, dlg: ft.AlertDialog):
        page = self._obter_pagina()
        if not page:
            return
        if hasattr(page, "close"):
            page.close(dlg)
        else:
            dlg.open = False
            page.update()

    def _abrir_dialog_edicao_cartao(self, cartao):
        page = self._obter_pagina()
        if not page:
            return

        txt_nome = ft.TextField(
            label="Nome do Cartão",
            value=cartao.nome or "",
            expand=True,
            autofocus=True,
        )
        txt_limite = ft.TextField(
            label="Limite (R$)",
            value=f"{float(cartao.limite or 0.0):.2f}".replace(".", ","),
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        txt_fechamento = ft.TextField(
            label="Dia Fechamento",
            value=str(cartao.dia_fechamento or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        txt_vencimento = ft.TextField(
            label="Dia Vencimento",
            value=str(cartao.dia_vencimento or ""),
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )

        possui_ativo = hasattr(cartao, "ativo")
        chk_ativo = ft.Checkbox(
            label="Cartão ativo",
            value=bool(getattr(cartao, "ativo", True)),
            visible=possui_ativo,
        )

        def _confirmar_edicao(e=None):
            nome = (txt_nome.value or "").strip()
            fech_str = (txt_fechamento.value or "").strip()
            venc_str = (txt_vencimento.value or "").strip()

            if not nome or not fech_str.isdigit() or not venc_str.isdigit():
                mostrar_mensagem(page, "❌ Preencha os campos do cartão corretamente!")
                return

            try:
                limite = self._parse_limite(txt_limite.value)
                dia_fechamento = int(fech_str)
                dia_vencimento = int(venc_str)

                if (
                    limite <= 0
                    or not (1 <= dia_fechamento <= 31)
                    or not (1 <= dia_vencimento <= 31)
                ):
                    mostrar_mensagem(
                        page,
                        "❌ Informe limite maior que zero e dias entre 1 e 31!",
                    )
                    return

                if possui_ativo:
                    cartao.ativo = bool(chk_ativo.value)

                salvar_cartao(
                    cartao_id=cartao.id,
                    nome=nome,
                    limite=limite,
                    dia_fechamento=dia_fechamento,
                    dia_vencimento=dia_vencimento,
                    perfil_id=self.perfil_ativo_id[0],
                )

                self._fechar_dialogo(dlg)
                mostrar_mensagem(page, "✅ Cartão atualizado com sucesso!")
                self.atualizar(self._ultimo_dados)
                self.on_atualizar()
            except Exception as ex:
                mostrar_mensagem(page, f"❌ Erro ao atualizar cartão: {ex}")

        linha_1 = ft.Row([txt_nome, txt_limite], spacing=10)
        linha_2 = ft.Row([txt_fechamento, txt_vencimento], spacing=10)
        linha_botoes = ft.Row(
            [
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: self._fechar_dialogo(dlg),
                ),
                ft.FilledButton(
                    "Salvar",
                    icon=ft.Icons.SAVE,
                    bgcolor=ft.Colors.BLUE_600,
                    color=ft.Colors.WHITE,
                    on_click=_confirmar_edicao,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
        )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Editar Cartão: {cartao.nome.title()}"),
            content=ft.Column(
                [
                    linha_1,
                    linha_2,
                    chk_ativo,
                    ft.Container(
                        content=linha_botoes,
                        padding=ft.Padding(top=6, bottom=0, left=0, right=0),
                    ),
                ],
                tight=True,
                spacing=12,
                width=460,
            ),
        )

        self._abrir_dialogo(dlg)

    def _abrir_dialog_fatura_cartao(self, cartao, dlg_atual: ft.AlertDialog | None = None):
        page = self._obter_pagina()
        if not page:
            return

        if dlg_atual is not None:
            self._fechar_dialogo(dlg_atual)

        mes, ano = self.obter_periodo()
        itens = buscar_transacoes_cartao_periodo(cartao.id, mes, ano)

        dlg = ft.AlertDialog(modal=True)

        def _excluir_item_fatura(transacao_id):
            if not transacao_id:
                return
            if remover_transacao(transacao_id):
                mostrar_mensagem(page, "✅ Item removido da fatura!")
                self.atualizar(self._ultimo_dados)
                self.on_atualizar()
                self._abrir_dialog_fatura_cartao(cartao, dlg_atual=dlg)
            else:
                mostrar_mensagem(page, "❌ Não foi possível remover o item.")

        if not itens:
            corpo_itens = ft.Container(
                content=ft.Text(
                    f"Nenhum lançamento encontrado para {cartao.nome} em {mes:02d}/{ano}.",
                    color=ft.Colors.GREY_400,
                ),
                padding=ft.Padding(top=8, bottom=8, left=0, right=0),
            )
            total_fatura = 0.0
        else:
            linhas_itens = []
            total_fatura = 0.0
            for item in itens:
                valor = float(getattr(item, "valor", 0.0) or 0.0)
                tipo = getattr(item, "tipo", "Saída")
                total_fatura += valor if tipo != "Entrada" else -valor

                dt = (
                    self.extrair_data(item)
                    if callable(self.extrair_data)
                    else getattr(item, "data", "")
                )
                data_txt = (
                    dt.strftime("%d/%m/%Y") if hasattr(dt, "strftime") else str(dt or "-")
                )
                desc_txt = getattr(item, "descricao", "") or "Sem descrição"
                parcela_atual = getattr(item, "parcela_atual", None)
                total_parcelas = getattr(item, "total_parcelas", None)
                if parcela_atual and total_parcelas and int(total_parcelas) > 1:
                    desc_txt = f"{desc_txt} ({parcela_atual}/{total_parcelas})"

                cor_valor = (
                    ft.Colors.GREEN_400 if tipo == "Entrada" else ft.Colors.RED_400
                )
                item_id = getattr(item, "id", None)

                btn_excluir_item = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    icon_size=18,
                    tooltip="Excluir item",
                    on_click=lambda e, tid=item_id: _excluir_item_fatura(tid),
                )

                linhas_itens.append(
                    ft.Row(
                        [
                            ft.Text(data_txt, width=82, size=12, color=ft.Colors.GREY_300),
                            ft.Text(desc_txt, expand=True, size=12),
                            ft.Text(
                                self.formatar(valor),
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=cor_valor,
                            ),
                            btn_excluir_item,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

            corpo_itens = ft.Column(
                linhas_itens,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                height=240,
            )

        dlg.title = ft.Text(f"Fatura — {cartao.nome} ({mes:02d}/{ano})")
        dlg.content = ft.Column(
            [
                corpo_itens,
                ft.Divider(height=1),
                ft.Row(
                    [
                        ft.Text("Total no período:", weight=ft.FontWeight.BOLD),
                        ft.Text(
                            self.formatar(total_fatura),
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_300,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            tight=True,
            spacing=10,
            width=480,
        )
        dlg.actions = [
            ft.TextButton(
                "Fechar",
                on_click=lambda e: self._fechar_dialogo(dlg),
            )
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.END

        self._abrir_dialogo(dlg)

    def fechar_formulario(self, e=None):
        self.cartao_editando_id = None
        self.btn_salvar.text = "Salvar Cartão"
        self.painel_formulario.visible = False
        self.btn_adicionar.visible = True
        if self.page_ref:
            self.page_ref.update()

    def _parse_limite(self, raw_val: str) -> float:
        limpo = (
            str(raw_val or "")
            .replace("R$", "")
            .replace("r$", "")
            .replace(" ", "")
            .strip()
        )
        if "," in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        return float(limpo)

    def salvar(self, e=None):
        if not self.perfil_ativo_id[0]:
            mostrar_mensagem(self.page_ref, "❌ Selecione um perfil primeiro!")
            return

        nome = (self.txt_nome_cartao.value or "").strip()
        fech_str = (self.txt_dia_fechamento.value or "").strip()
        venc_str = (self.txt_dia_vencimento.value or "").strip()

        if not nome or not fech_str.isdigit() or not venc_str.isdigit():
            mostrar_mensagem(self.page_ref, "❌ Preencha os campos do cartão corretamente!")
            return

        try:
            limite = self._parse_limite(self.txt_limite_cartao.value)
            dia_fechamento = int(fech_str)
            dia_vencimento = int(venc_str)

            if (
                limite <= 0
                or not (1 <= dia_fechamento <= 31)
                or not (1 <= dia_vencimento <= 31)
            ):
                mostrar_mensagem(
                    self.page_ref,
                    "❌ Informe limite maior que zero e dias entre 1 e 31!",
                )
                return

            salvar_cartao(
                cartao_id=self.cartao_editando_id,
                nome=nome,
                limite=limite,
                dia_fechamento=dia_fechamento,
                dia_vencimento=dia_vencimento,
                perfil_id=self.perfil_ativo_id[0],
            )

            self.cartao_editando_id = None
            self.btn_salvar.text = "Salvar Cartão"
            self.txt_nome_cartao.value = ""
            self.txt_limite_cartao.value = ""
            self.txt_dia_fechamento.value = ""
            self.txt_dia_vencimento.value = ""

            mostrar_mensagem(self.page_ref, "✅ Cartão salvo com sucesso!")
            self.atualizar(self._ultimo_dados)
            self.on_atualizar()
            if self.page_ref:
                self.page_ref.run_task(self.txt_nome_cartao.focus)
        except Exception as ex:
            mostrar_mensagem(self.page_ref, f"❌ Erro ao salvar cartão: {ex}")

    def _excluir_cartao(self, cartao_id):
        if deletar_cartao(cartao_id):
            if self.cartao_selecionado_id == cartao_id:
                self.cartao_selecionado_id = None
            mostrar_mensagem(self.page_ref, "✅ Cartão removido!")
            self.atualizar(self._ultimo_dados)
            self.on_atualizar()

    def _obter_pagina(self) -> ft.Page | None:
        p = self.page_ref
        if callable(p):
            p = p()
        elif isinstance(p, (list, tuple)) and p:
            p = p[0]
        return p

    def atualizar(self, dados: dict = None):
        if dados is not None:
            self._ultimo_dados = dados

        self.tabela.rows = []

        if not self.perfil_ativo_id[0]:
            self._atualizar_grafico_cartoes([], dados=dados)
            return

        cartoes_ativos = self._filtrar_cartoes_ativos(
            buscar_cartoes_do_perfil(self.perfil_ativo_id[0])
        )

        _, filtro_status = self.obter_filtros()
        linhas = []
        cartoes_exibidos = []

        for cartao in cartoes_ativos:
            lims = calcular_limites_cartao(cartao.id)
            total = lims["total"]
            usado = lims["comprometido"]
            disp = lims["disponivel"]
            perc = (usado / total) if total > 0 else 0.0

            if filtro_status == "Com limite livre" and disp <= 0:
                continue
            if filtro_status == "Alto uso (>=70%)" and perc < 0.7:
                continue

            cartoes_exibidos.append(cartao)

            selecionado = cartao.id == self.cartao_selecionado_id
            celula_nome = ft.DataCell(
                ft.TextButton(
                    content=ft.Text(
                        cartao.nome,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE_300 if selecionado else ft.Colors.WHITE,
                    ),
                    style=ft.ButtonStyle(
                        padding=ft.Padding(left=2, right=2, top=0, bottom=0)
                    ),
                    on_click=lambda e, c=cartao: self._ao_selecionar_cartao(c),
                )
            )

            btn_fatura = ft.IconButton(
                icon=ft.Icons.RECEIPT_LONG,
                icon_color=ft.Colors.AMBER_400,
                tooltip="Ver itens da fatura",
                on_click=lambda e, c=cartao: self._abrir_dialog_fatura_cartao(c),
            )
            btn_editar = ft.IconButton(
                icon=ft.Icons.EDIT,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Editar cartão",
                on_click=lambda e, c=cartao: self._abrir_dialog_edicao_cartao(c),
            )
            btn_excluir = ft.IconButton(
                icon=ft.Icons.DELETE,
                icon_color=ft.Colors.RED_400,
                tooltip="Excluir cartão",
                on_click=lambda e, cid=cartao.id: self._excluir_cartao(cid),
            )

            linhas.append(
                ft.DataRow(
                    selected=selecionado,
                    cells=[
                        celula_nome,
                        ft.DataCell(ft.Text(self.formatar(total), size=12)),
                        ft.DataCell(
                            ft.Text(self.formatar(usado), size=12, color=ft.Colors.RED_400)
                        ),
                        ft.DataCell(
                            ft.Text(
                                self.formatar(disp),
                                size=12,
                                color=ft.Colors.GREEN_400,
                                weight=ft.FontWeight.BOLD,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"Dia {cartao.dia_fechamento}"
                                if cartao.dia_fechamento
                                else "-",
                                size=12,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"Dia {cartao.dia_vencimento}"
                                if cartao.dia_vencimento
                                else "-",
                                size=12,
                            )
                        ),
                        ft.DataCell(btn_fatura),
                        ft.DataCell(ft.Row([btn_editar, btn_excluir], spacing=0)),
                    ],
                )
            )

        self.tabela.rows = linhas
        self._atualizar_grafico_cartoes(cartoes_exibidos, dados=dados)