from contextlib import contextmanager
from database.connection import get_db

@contextmanager
def obter_sessao():
    with get_db() as session:
        yield session