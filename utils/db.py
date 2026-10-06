from contextlib import contextmanager
from database.connection import get_db

@contextmanager
def obter_sessao():
    db = get_db()
    if hasattr(db, "__enter__"):
        with db as session:
            yield session
    elif hasattr(db, "__next__"):
        session = next(db)
        try:
            yield session
        finally:
            try:
                next(db)
            except StopIteration:
                pass
    else:
        try:
            yield db
        finally:
            if hasattr(db, "close"):
                try:
                    db.close()
                except Exception:
                    pass