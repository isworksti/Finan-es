from datetime import date, datetime

from datetime import datetime, date

def extrair_data(transacao):
    if not transacao or not hasattr(transacao, "data"):
        return None
        
    val = transacao.data
    
    if isinstance(val, date):
        return val
    elif isinstance(val, datetime):
        return val.date()
    elif isinstance(val, str):
        # Tenta converter os formatos de string mais comuns do banco de dados
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                pass
    return None