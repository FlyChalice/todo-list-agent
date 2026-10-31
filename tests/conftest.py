import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 确保从 tests/ 目录运行时能导入项目根目录的 main.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from main import TODOS  # noqa: E402


@pytest.fixture
def client():
    """每个测试用例使用干净的空白内存数据。"""
    TODOS.clear()
    with TestClient(main.app) as c:
        yield c
    TODOS.clear()
