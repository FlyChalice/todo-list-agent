"""一、背景与目标：FastAPI 版 TodoList，数据存于进程内存，服务重启清空。"""

import threading
import time
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="TodoList")

# 内存任务列表，数组顺序即「手动排序」顺序；服务重启后清空。
TODOS: list["Todo"] = []
LOCK = threading.Lock()

SORT_MODES = {"manual", "createdDesc", "createdAsc", "incompleteFirst"}
FILTERS = {"all", "incomplete", "completed"}


class Todo(BaseModel):
    """单条任务。Python 内部用 snake_case，对外 JSON 用 camelCase。"""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    text: str
    is_completed: bool = Field(alias="isCompleted")
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")


def _error(status: int, code: str, message: str) -> JSONResponse:
    """统一的失败响应结构。"""
    return JSONResponse(
        status_code=status, content={"ok": False, "code": code, "message": message}
    )


def validate_text(raw) -> tuple[str, JSONResponse | None]:
    """校验任务文本，返回 (trim 后文本, 错误响应或 None)。"""
    if not isinstance(raw, str):
        return "", _error(400, "E1001", "任务内容不能为空")
    text = raw.strip()
    if not text:
        return "", _error(400, "E1001", "任务内容不能为空")
    if len(text) > 100:
        return "", _error(400, "E1002", "任务内容不能超过 100 个字符")
    return text, None


def _sorted(items: list[Todo], sort: str) -> list[Todo]:
    """在副本上排序，绝不写回 TODOS（保护手动顺序）。"""
    if sort == "createdDesc":
        return sorted(items, key=lambda t: t.created_at, reverse=True)
    if sort == "createdAsc":
        return sorted(items, key=lambda t: t.created_at)
    if sort == "incompleteFirst":
        return sorted(items, key=lambda t: (t.is_completed, t.created_at))
    return items


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"title": "TodoList"})


@app.get("/api/todos")
def list_todos(
    query: str = "",
    filter_: str = Query("all", alias="filter"),
    sort: str = "manual",
):
    if filter_ not in FILTERS:
        filter_ = "all"
    if sort not in SORT_MODES:
        sort = "manual"

    with LOCK:
        items = list(TODOS)

    if filter_ == "completed":
        items = [t for t in items if t.is_completed]
    elif filter_ == "incomplete":
        items = [t for t in items if not t.is_completed]

    keyword = query.strip().lower()
    if keyword:
        items = [t for t in items if keyword in t.text.lower()]

    items = _sorted(items, sort)
    return {"ok": True, "data": [t.model_dump(by_alias=True) for t in items]}


@app.post("/api/todos", status_code=201)
def create_todo(payload: dict = Body(...)):
    text, error = validate_text(payload.get("text"))
    if error is not None:
        return error

    now = int(time.time() * 1000)
    todo = Todo(
        id=str(uuid.uuid4()),
        text=text,
        is_completed=False,
        created_at=now,
        updated_at=now,
    )
    with LOCK:
        TODOS.append(todo)
    return {"ok": True, "data": todo.model_dump(by_alias=True)}


@app.patch("/api/todos/{todo_id}")
def update_todo(todo_id: str, payload: dict = Body(...)):
    has_text = "text" in payload
    has_completed = "isCompleted" in payload
    if not has_text and not has_completed:
        return _error(400, "E1004", "请求参数不合法")

    if has_text and not isinstance(payload["text"], str):
        return _error(400, "E1004", "请求参数不合法")
    if has_completed and not isinstance(payload["isCompleted"], bool):
        return _error(400, "E1004", "请求参数不合法")

    text = None
    if has_text:
        text, error = validate_text(payload["text"])
        if error is not None:
            return error

    with LOCK:
        target = next((t for t in TODOS if t.id == todo_id), None)
        if target is None:
            return _error(404, "E1003", "任务不存在，可能已被删除")

        if text is not None:
            target.text = text
        if has_completed:
            target.is_completed = payload["isCompleted"]
        target.updated_at = int(time.time() * 1000)
        return {"ok": True, "data": target.model_dump(by_alias=True)}


@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: str):
    with LOCK:
        for index, todo in enumerate(TODOS):
            if todo.id == todo_id:
                TODOS.pop(index)
                return {"ok": True, "data": True}
    return _error(404, "E1003", "任务不存在，可能已被删除")


@app.post("/api/todos/{todo_id}/move")
def move_todo(todo_id: str, payload: dict = Body(...)):
    direction = payload.get("direction")
    if direction not in ("up", "down"):
        return _error(400, "E1004", "请求参数不合法")

    with LOCK:
        if not any(t.id == todo_id for t in TODOS):
            return _error(404, "E1003", "任务不存在，可能已被删除")

        index = next(i for i, t in enumerate(TODOS) if t.id == todo_id)
        new_index = index - 1 if direction == "up" else index + 1
        if 0 <= new_index < len(TODOS):
            TODOS[index], TODOS[new_index] = TODOS[new_index], TODOS[index]

        return {"ok": True, "data": [t.model_dump(by_alias=True) for t in TODOS]}


@app.post("/api/todos/clear-completed")
def clear_completed():
    with LOCK:
        before = len(TODOS)
        TODOS[:] = [t for t in TODOS if not t.is_completed]
        return {"ok": True, "data": {"removed": before - len(TODOS)}}
