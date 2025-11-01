import pandas as pd
import textwrap

def formatar_numero_seguro(valor, decimais=1):
    try:
        if pd.isna(valor) or valor is None:
            return "0"
        
        valor_numerico = float(valor)
        
        if abs(valor_numerico) < 0.001:
            return "0"
        
        if decimais == 0:
            return f"{valor_numerico:,.0f}".replace(',', '.')
        else:
            formatado = f"{valor_numerico:,.{decimais}f}"
            if '.' in formatado:
                partes = formatado.split('.')
                parte_inteira = partes[0].replace(',', '.')
                parte_decimal = partes[1]
                return f"{parte_inteira},{parte_decimal}"
            else:
                return formatado.replace(',', '.')
                
    except (ValueError, TypeError, AttributeError):
        return "Erro"

def formatar_numero_com_pontos(numero, casas_decimais=1):
    if pd.isna(numero) or numero is None:
        return "0"
    
    try:
        num = float(numero)
        if num == 0:
            return "0"
        if casas_decimais == 0:
            formatado = f"{num:,.0f}"
        else:
            formatado = f"{num:,.{casas_decimais}f}"
        if '.' in formatado:
            partes = formatado.split('.')
            parte_inteira = partes[0]
            parte_decimal = partes[1] if len(partes) > 1 else ""
            parte_inteira = parte_inteira.replace(',', '.')
            if parte_decimal and casas_decimais > 0:
                return f"{parte_inteira},{parte_decimal}"
            else:
                return parte_inteira
        else:
            return formatado.replace(',', '.')
            
    except (ValueError, TypeError, AttributeError) as e:
        try:
            return f"{float(numero):,.{casas_decimais}f}".replace(',', '.')
        except:
            return str(numero) if numero is not None else "0"

def criar_formato_tick_customizado(valores):
    if not valores:
        return {}
    
    valores_formatados = []
    for val in valores:
        if val >= 1000000:
            valores_formatados.append(f"{formatar_numero_com_pontos(val/1000000, 1)}M")
        elif val >= 1000:
            valores_formatados.append(f"{formatar_numero_com_pontos(val/1000, 0)}k")
        else:
            valores_formatados.append(formatar_numero_com_pontos(val, 0))
    
    return dict(zip(valores, valores_formatados))


def wrap_label(name, width=30):
    if pd.isna(name):
        return ""
    return "<br>".join(textwrap.wrap(str(name), width))
