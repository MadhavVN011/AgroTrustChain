import os
import sys

import pytest

# Make the app modules importable both from the repository (tests/ next to src/)
# and inside the Docker image (tests/ inside the app directory).
_here = os.path.dirname(os.path.abspath(__file__))
for candidate in (os.path.join(_here, "..", "src"), os.path.join(_here, "..")):
    if os.path.exists(os.path.join(candidate, "HashChain.py")):
        sys.path.insert(0, os.path.abspath(candidate))
        break


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rows = []

    def execute(self, sql, *params):
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            params = tuple(params[0])
        self.db.executed.append((sql, params))
        self.rows = list(self.db.handler(sql, params) or [])
        return self

    @property
    def description(self):
        return [(name,) for name in self.db.columns]

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def commit(self):
        pass

    def close(self):
        pass


class FakeConnection:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class FakeDatabase:
    """Stands in for pyodbc. Set .handler to a function (sql, params) -> rows."""

    def __init__(self):
        self.executed = []
        self.columns = []  # column names reported by cursor.description
        self.handler = lambda sql, params: []

    def connect(self, *args, **kwargs):
        return FakeConnection(self)


@pytest.fixture
def fake_db(monkeypatch):
    import pyodbc
    db = FakeDatabase()
    monkeypatch.setattr(pyodbc, "connect", db.connect)
    return db
