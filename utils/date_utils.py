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

def obter_mes_ano_fatura(data_transacao: date, dia_fechamento: int):
    if not dia_fechamento:
        return data_transacao.month, data_transacao.year

    # Se a compra foi feita no dia do fechamento ou depois, vai para a fatura do mês seguinte
    if data_transacao.day >= dia_fechamento:
        mes = data_transacao.month + 1
        ano = data_transacao.year
        if mes > 12:
            mes = 1
            ano += 1
        return mes, ano

    return data_transacao.month, data_transacao.year