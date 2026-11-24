from datetime import date, datetime


def extrair_data(transacao):
    if not transacao or not hasattr(transacao, "data"):
        return None

    val = transacao.data

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        texto = val.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                pass
    return None