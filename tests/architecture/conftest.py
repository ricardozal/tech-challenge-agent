import pytest

from tests.support import testdb


@pytest.fixture(scope="session")
def test_db():
    if not testdb.available():
        pytest.skip("Postgres not running; run `make up-db`")
    db = testdb.create()
    yield db
    testdb.drop(db)
