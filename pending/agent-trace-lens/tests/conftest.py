from __future__ import annotations

import pytest

from agent_trace_lens.storage import SQLiteStorage
from agent_trace_lens.tracer import Tracer


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "traces.db")


@pytest.fixture()
def storage(db_path):
    s = SQLiteStorage(db_path)
    yield s
    s.close()


@pytest.fixture()
def tracer(storage):
    return Tracer(storage=storage)
