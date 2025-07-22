# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

# 1) Motor SQLite en memoria
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2) Fixture que crea las tablas antes y las destruye después
@pytest.fixture(scope="session", autouse=True)
def init_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

# 3) Fixture de sesión para cada test
@pytest.fixture()
def db_session(init_db):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

# 4) Override de la dependencia get_db
@pytest.fixture()
def client(db_session, monkeypatch):
    def _get_test_db():
        try:
            yield db_session
        finally:
            pass

    monkeypatch.setattr("app.core.database.get_db", lambda: _get_test_db())
    return TestClient(app)
