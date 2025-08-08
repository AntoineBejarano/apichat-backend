import re
from typing import List, Any

def truncate_words(text: str, max_words: int = 50) -> str:
    """Trunca texto a un número máximo de palabras"""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."

def format_database_tables(tables: List[Any]) -> str:
    """Formatea una lista de tablas de base de datos de manera legible"""
    if not tables:
        return "No se encontraron tablas en la base de datos."
    
    # Extraer nombres de tablas (asumiendo que pueden venir como tuplas o strings)
    table_names = []
    for table in tables:
        if isinstance(table, tuple):
            table_names.append(table[0])
        elif isinstance(table, str):
            table_names.append(table)
        else:
            table_names.append(str(table))
    
    # Ordenar alfabéticamente
    table_names.sort()
    
    # Agrupar por categorías si hay muchas tablas
    if len(table_names) > 20:
        # Agrupar por prefijos comunes
        groups = {}
        for table in table_names:
            prefix = table.split('_')[0] if '_' in table else 'otros'
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(table)
        
        # Formatear con grupos
        result = "📊 **Tablas encontradas en tu base de datos:**\n\n"
        for prefix, tables_in_group in sorted(groups.items()):
            result += f"**{prefix.title()}:**\n"
            for table in tables_in_group:
                result += f"• {table}\n"
            result += "\n"
    else:
        # Lista simple si hay pocas tablas
        result = "📊 **Tablas encontradas en tu base de datos:**\n\n"
        for table in table_names:
            result += f"• {table}\n"
    
    result += f"\n**Total:** {len(table_names)} tablas\n\n"
    result += "Puedo ayudarte a realizar consultas en estas tablas, insertar, actualizar o eliminar datos, o incluso ayudarte a entender los datos en estas tablas. ¿Qué te gustaría hacer?"
    
    return result

def format_query_results(results: List[Any], query_description: str = "") -> str:
    """Formatea resultados de consultas de manera legible"""
    if not results:
        return f"No se encontraron resultados para la consulta: {query_description}"
    
    result = f"📋 **Resultados de la consulta:**\n"
    if query_description:
        result += f"*{query_description}*\n\n"
    
    # Si hay muchos resultados, mostrar solo los primeros
    max_results = 10
    if len(results) > max_results:
        result += f"*Mostrando los primeros {max_results} resultados de {len(results)} totales:*\n\n"
        results = results[:max_results]
    
    for i, row in enumerate(results, 1):
        if isinstance(row, (list, tuple)):
            result += f"{i}. {', '.join(str(cell) for cell in row)}\n"
        else:
            result += f"{i}. {row}\n"
    
    if len(results) > max_results:
        result += f"\n... y {len(results) - max_results} resultados más."
    
    return result
