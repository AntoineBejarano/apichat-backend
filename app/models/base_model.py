from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.declarative import declared_attr

class Base(DeclarativeBase):
    pass

class BaseTable(Base):
    """Clase base para todos los modelos de tabla"""
    
    # Hacer que sea una clase abstracta
    __abstract__ = True
    
    # Método para generar automáticamente el nombre de la tabla
    @declared_attr
    def __tablename__(cls):
        # Convertir CamelCase a snake_case para el nombre de la tabla
        import re
        name = re.sub('(?!^)([A-Z][a-z]+)', r'_\1', cls.__name__)
        return name.lower()
