import flet as ft


def _criar_card_kpi(titulo, controle_texto, icone, cor_icone):
    """Cria um card individual para exibição de métricas/KPIs."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icone, size=30, color=cor_icone),
                ft.Column(
                    [
                        ft.Text(
                            titulo,
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.GREY_300,
                        ),
                        controle_texto,
                    ],
                    spacing=2,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=15,
        border=ft.Border.all(1, ft.Colors.WHITE_24),
        border_radius=10,
        expand=True,
    )


def criar_linha_kpis(
    txt_entradas: ft.Text,
    txt_saidas: ft.Text,
    txt_saldo: ft.Text,
    txt_fatura_total: ft.Text,
) -> ft.Row:
    """Retorna uma Row com todos os 4 cards de KPI do dashboard."""
    return ft.Row(
        [
            _criar_card_kpi(
                "Entradas no Mês",
                txt_entradas,
                ft.Icons.ARROW_UPWARD,
                ft.Colors.GREEN_400,
            ),
            _criar_card_kpi(
                "Saídas no Mês",
                txt_saidas,
                ft.Icons.ARROW_DOWNWARD,
                ft.Colors.RED_400,
            ),
            _criar_card_kpi(
                "Saldo Líquido",
                txt_saldo,
                ft.Icons.ACCOUNT_BALANCE_WALLET,
                ft.Colors.BLUE_400,
            ),
            _criar_card_kpi(
                "Fatura de Crédito",
                txt_fatura_total,
                ft.Icons.CREDIT_CARD,
                ft.Colors.AMBER_400,
            ),
        ],
        spacing=15,
    )