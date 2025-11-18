import pytest
from sqlalchemy import text
import src.database.connection as connection


@pytest.fixture(autouse=True)
def use_sqlite(monkeypatch):
    # Override DATABASE_URL to use SQLite in-memory
    monkeypatch.setattr(connection, "DATABASE_URL", "sqlite:///:memory:")
    # Recreate engine and SessionLocal with SQLite
    engine = connection.create_db_engine()
    monkeypatch.setattr(connection, "engine", engine)
    connection.SessionLocal.configure(bind=engine)
    yield
    engine.dispose()


def test_create_db_engine_returns_engine():
    engine = connection.create_db_engine()
    assert engine is not None
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_create_db_engine_returns_engine():
    engine = connection.create_db_engine()
    assert engine is not None
    # Should be able to run a simple query
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_get_session_and_get_db():
    # get_session returns a Session
    session = connection.get_session()
    assert session is not None
    session.close()

    # get_db yields a Session and closes it
    gen = connection.get_db()
    db = next(gen)
    assert db is not None
    # Simulate exception to trigger rollback
    try:
        raise Exception("boom")
    except Exception:
        with pytest.raises(Exception):
            gen.throw(Exception("boom"))


def test_check_db_health_success():
    assert connection.check_db_health() is True


def test_check_db_health_failure(monkeypatch):
    def bad_connect(*a, **kw): raise Exception("fail")
    monkeypatch.setattr(connection.engine, "connect", bad_connect)
    assert connection.check_db_health() is False


def test_get_db_stats(monkeypatch):
    stats = connection.get_db_stats()
    assert "pool_size" in stats
    assert "checkedin" in stats

    # Force exception path
    monkeypatch.setattr(connection, "engine", None)
    stats = connection.get_db_stats()
    assert "error" in stats


def test_init_and_drop_db(monkeypatch):
    # Patch Base.metadata.create_all/drop_all to avoid touching real DB
    class FakeMeta:
        def create_all(self, bind=None): self.called = True
        def drop_all(self, bind=None): self.dropped = True
    class FakeBase: metadata = FakeMeta()

    monkeypatch.setattr("src.database.models.Base", FakeBase)

    assert connection.init_db() is True
    assert connection.drop_db() is True


def test_execute_query_and_insert():
    # Simple query
    results = connection.execute_query("SELECT 1")
    assert results[0][0] == 1

    # Parameterized query
    results = connection.execute_query("SELECT :x", {"x": 42})
    assert results[0][0] == 42

    # Insert (using temp table)
    connection.execute_query("CREATE TABLE IF NOT EXISTS temp (id INTEGER)")
    ok = connection.execute_insert("INSERT INTO temp (id) VALUES (:id)", {"id": 1})
    assert ok is True
    results = connection.execute_query("SELECT id FROM temp")
    assert results[0][0] == 1


def test_execute_query_failure(monkeypatch):
    monkeypatch.setattr(connection.engine, "connect", lambda: (_ for _ in ()).throw(Exception("fail")))
    results = connection.execute_query("SELECT 1")
    assert results is None


def test_execute_insert_failure(monkeypatch):
    monkeypatch.setattr(connection.engine, "begin", lambda: (_ for _ in ()).throw(Exception("fail")))
    ok = connection.execute_insert("INSERT INTO temp (id) VALUES (1)")
    assert ok is False


def test_close_db():
    connection.close_db()
    # After dispose, engine should still be usable
    engine = connection.create_db_engine()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
