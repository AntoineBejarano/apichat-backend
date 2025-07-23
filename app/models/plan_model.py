from sqlalchemy import Column, Integer, String, Float, Boolean
from app.models.base_model import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    stripe_price_id = Column(String, unique=True, nullable=False)
    price = Column(Float, nullable=False)
    features = Column(String)
    is_active = Column(Boolean, default=True)

    # Token mensual permitido (principal métrica de uso)
    token_limit = Column(Integer, nullable=False)

    # Límites de recursos por usuario según su plan
    max_agents = Column(Integer, default=1, nullable=False)
    max_strategies = Column(Integer, default=1, nullable=False)
    max_apps = Column(Integer, default=1, nullable=False)
    max_proxies = Column(Integer, default=0, nullable=False)
    max_databases = Column(Integer, default=0, nullable=False)


    # Puedes añadir más si en el futuro limitas chats, bases de datos, etc.
