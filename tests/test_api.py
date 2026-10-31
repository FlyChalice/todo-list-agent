from main import TODOS, Todo


def test_home_returns_200_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def _seed(id_, text, is_completed=False, created_at=1000):
    """直接向内存列表播种一条任务（字段用 Python 内部名称）。"""
    TODOS.append(
        Todo(
            id=id_,
            text=text,
            is_completed=is_completed,
            created_at=created_at,
            updated_at=created_at,
        )
    )


def test_get_todos_empty(client):
    resp = client.get("/api/todos")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": []}


def test_get_todos_manual_order_and_camel_case(client):
    _seed("a", "任务A", created_at=1000)
    _seed("b", "任务B", created_at=1002)
    _seed("c", "任务C", created_at=1001)

    data = client.get("/api/todos").json()["data"]

    # 默认 sort=manual：按内存数组顺序返回，与 createdAt 无关
    assert [t["text"] for t in data] == ["任务A", "任务B", "任务C"]
    # 响应字段必须是 camelCase
    assert set(data[0]) == {"id", "text", "isCompleted", "createdAt", "updatedAt"}
    assert data[0]["isCompleted"] is False


def test_sort_created_desc(client):
    _seed("a", "A", created_at=1000)
    _seed("b", "B", created_at=1003)
    _seed("c", "C", created_at=1001)

    data = client.get("/api/todos", params={"sort": "createdDesc"}).json()["data"]
    assert [t["text"] for t in data] == ["B", "C", "A"]


def test_sort_created_asc(client):
    _seed("a", "A", created_at=1003)
    _seed("b", "B", created_at=1000)
    _seed("c", "C", created_at=1001)

    data = client.get("/api/todos", params={"sort": "createdAsc"}).json()["data"]
    assert [t["text"] for t in data] == ["B", "C", "A"]


def test_sort_incomplete_first(client):
    _seed("a", "A", is_completed=True, created_at=1000)
    _seed("b", "B", is_completed=False, created_at=1003)
    _seed("c", "C", is_completed=False, created_at=1001)
    _seed("d", "D", is_completed=True, created_at=1002)

    data = client.get("/api/todos", params={"sort": "incompleteFirst"}).json()["data"]
    # 未完成组在前、已完成组在后，组内按 createdAt 升序
    assert [t["text"] for t in data] == ["C", "B", "A", "D"]


def test_sort_does_not_mutate_manual_order(client):
    _seed("a", "A", created_at=1000)
    _seed("b", "B", created_at=1002)
    _seed("c", "C", created_at=1001)

    client.get("/api/todos", params={"sort": "createdDesc"})

    data = client.get("/api/todos").json()["data"]
    assert [t["text"] for t in data] == ["A", "B", "C"]


def test_filter_completed(client):
    _seed("a", "A", is_completed=True)
    _seed("b", "B", is_completed=False)

    data = client.get("/api/todos", params={"filter": "completed"}).json()["data"]
    assert [t["id"] for t in data] == ["a"]


def test_filter_incomplete(client):
    _seed("a", "A", is_completed=True)
    _seed("b", "B", is_completed=False)

    data = client.get("/api/todos", params={"filter": "incomplete"}).json()["data"]
    assert [t["id"] for t in data] == ["b"]


def test_query_is_case_insensitive_fuzzy(client):
    _seed("a", "Buy milk")
    _seed("b", "买牛奶")
    _seed("c", "读书")

    assert [t["id"] for t in client.get("/api/todos", params={"query": "buy"}).json()["data"]] == ["a"]
    assert [t["id"] for t in client.get("/api/todos", params={"query": "MILK"}).json()["data"]] == ["a"]
    assert [t["id"] for t in client.get("/api/todos", params={"query": "牛"}).json()["data"]] == ["b"]


def test_query_and_filter_combine(client):
    _seed("a", "买牛奶", is_completed=True)
    _seed("b", "买面包", is_completed=False)
    _seed("c", "读书", is_completed=False)

    data = client.get(
        "/api/todos", params={"query": "买", "filter": "incomplete"}
    ).json()["data"]
    assert [t["id"] for t in data] == ["b"]


def test_unknown_sort_and_filter_fall_back_to_defaults(client):
    _seed("a", "A", created_at=1001)
    _seed("b", "B", created_at=1000)

    data = client.get("/api/todos", params={"sort": "foo", "filter": "bar"}).json()["data"]
    assert [t["text"] for t in data] == ["A", "B"]


def test_create_todo_returns_201_and_trimmed(client):
    resp = client.post("/api/todos", json={"text": "  买牛奶  "})
    assert resp.status_code == 201

    body = resp.json()
    assert body["ok"] is True
    todo = body["data"]
    assert todo["text"] == "买牛奶"
    assert todo["isCompleted"] is False
    assert set(todo) == {"id", "text", "isCompleted", "createdAt", "updatedAt"}
    assert isinstance(todo["id"], str) and todo["id"]
    assert isinstance(todo["createdAt"], int) and todo["createdAt"] > 0
    assert todo["updatedAt"] == todo["createdAt"]


def test_created_todo_appears_in_list(client):
    client.post("/api/todos", json={"text": "买牛奶"})
    data = client.get("/api/todos").json()["data"]
    assert len(data) == 1
    assert data[0]["text"] == "买牛奶"


def test_create_todo_appends_to_end_of_manual_order(client):
    client.post("/api/todos", json={"text": "A"})
    client.post("/api/todos", json={"text": "B"})
    data = client.get("/api/todos").json()["data"]
    assert [t["text"] for t in data] == ["A", "B"]


def test_create_empty_text_returns_e1001(client):
    for payload in ({"text": ""}, {"text": "   "}):
        resp = client.post("/api/todos", json=payload)
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        assert body["code"] == "E1001"
        assert body["message"] == "任务内容不能为空"

    assert client.get("/api/todos").json()["data"] == []


def test_create_missing_or_non_string_text_returns_e1001(client):
    for payload in ({}, {"text": 123}, {"text": None}):
        resp = client.post("/api/todos", json=payload)
        assert resp.status_code == 400
        assert resp.json()["code"] == "E1001"

    assert client.get("/api/todos").json()["data"] == []


def test_create_100_chars_is_ok(client):
    resp = client.post("/api/todos", json={"text": "a" * 100})
    assert resp.status_code == 201
    assert resp.json()["data"]["text"] == "a" * 100


def test_create_101_chars_returns_e1002(client):
    resp = client.post("/api/todos", json={"text": "a" * 101})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "E1002"
    assert body["message"] == "任务内容不能超过 100 个字符"

    assert client.get("/api/todos").json()["data"] == []


def test_create_101_chars_with_spaces_returns_e1002(client):
    # trim 后仍为 101 字符
    resp = client.post("/api/todos", json={"text": "  " + "a" * 101 + "  "})
    assert resp.status_code == 400
    assert resp.json()["code"] == "E1002"


def _create(client, text):
    resp = client.post("/api/todos", json={"text": text})
    assert resp.status_code == 201
    return resp.json()["data"]


def test_patch_updates_text(client):
    todo = _create(client, "旧文本")

    resp = client.patch(f"/api/todos/{todo['id']}", json={"text": "  新文本  "})
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["text"] == "新文本"
    assert data["id"] == todo["id"]
    assert data["createdAt"] == todo["createdAt"]
    assert data["updatedAt"] >= data["createdAt"]


def test_patch_toggles_completed(client):
    todo = _create(client, "买牛奶")

    resp = client.patch(f"/api/todos/{todo['id']}", json={"isCompleted": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["isCompleted"] is True

    resp = client.patch(f"/api/todos/{todo['id']}", json={"isCompleted": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["isCompleted"] is False


def test_patch_text_and_completed_together(client):
    todo = _create(client, "旧文本")

    resp = client.patch(
        f"/api/todos/{todo['id']}", json={"text": "新文本", "isCompleted": True}
    )
    data = resp.json()["data"]
    assert data["text"] == "新文本"
    assert data["isCompleted"] is True


def test_patch_does_not_touch_other_todos(client):
    first = _create(client, "A")
    _create(client, "B")

    client.patch(f"/api/todos/{first['id']}", json={"isCompleted": True})

    data = client.get("/api/todos").json()["data"]
    assert [t["text"] for t in data] == ["A", "B"]
    assert data[1]["isCompleted"] is False


def test_patch_empty_text_returns_e1001_without_change(client):
    todo = _create(client, "原文本")

    resp = client.patch(f"/api/todos/{todo['id']}", json={"text": "   "})
    assert resp.status_code == 400
    assert resp.json()["code"] == "E1001"
    assert resp.json()["message"] == "任务内容不能为空"

    data = client.get("/api/todos").json()["data"]
    assert data[0]["text"] == "原文本"


def test_patch_101_chars_returns_e1002_without_change(client):
    todo = _create(client, "原文本")

    resp = client.patch(f"/api/todos/{todo['id']}", json={"text": "a" * 101})
    assert resp.status_code == 400
    assert resp.json()["code"] == "E1002"

    assert client.get("/api/todos").json()["data"][0]["text"] == "原文本"


def test_patch_unknown_id_returns_e1003(client):
    resp = client.patch("/api/todos/does-not-exist", json={"isCompleted": True})
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "E1003"
    assert body["message"] == "任务不存在，可能已被删除"


def test_patch_empty_body_returns_e1004(client):
    todo = _create(client, "买牛奶")

    resp = client.patch(f"/api/todos/{todo['id']}", json={})
    assert resp.status_code == 400
    assert resp.json()["code"] == "E1004"
    assert resp.json()["message"] == "请求参数不合法"


def test_patch_invalid_field_types_return_e1004(client):
    todo = _create(client, "买牛奶")

    for payload in (
        {"isCompleted": "yes"},
        {"isCompleted": 1},
        {"text": 123},
    ):
        resp = client.patch(f"/api/todos/{todo['id']}", json=payload)
        assert resp.status_code == 400
        assert resp.json()["code"] == "E1004"

    data = client.get("/api/todos").json()["data"][0]
    assert data["text"] == "买牛奶"
    assert data["isCompleted"] is False


def test_delete_todo_returns_true_and_removes_it(client):
    todo = _create(client, "买牛奶")

    resp = client.delete(f"/api/todos/{todo['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": True}

    assert client.get("/api/todos").json()["data"] == []


def test_delete_only_removes_target(client):
    first = _create(client, "A")
    second = _create(client, "B")

    client.delete(f"/api/todos/{first['id']}")

    data = client.get("/api/todos").json()["data"]
    assert [t["id"] for t in data] == [second["id"]]


def test_delete_unknown_id_returns_e1003(client):
    resp = client.delete("/api/todos/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "E1003"
    assert body["message"] == "任务不存在，可能已被删除"


def test_delete_twice_returns_e1003_second_time(client):
    todo = _create(client, "买牛奶")

    assert client.delete(f"/api/todos/{todo['id']}").status_code == 200
    resp = client.delete(f"/api/todos/{todo['id']}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "E1003"


def _seed_three():
    _seed("a", "A")
    _seed("b", "B")
    _seed("c", "C")


def test_move_down_swaps_with_next(client):
    _seed_three()

    resp = client.post("/api/todos/a/move", json={"direction": "down"})
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert [t["id"] for t in data] == ["b", "a", "c"]


def test_move_up_swaps_with_previous(client):
    _seed_three()

    resp = client.post("/api/todos/c/move", json={"direction": "up"})
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["data"]] == ["a", "c", "b"]


def test_move_persists_manual_order(client):
    _seed_three()

    client.post("/api/todos/a/move", json={"direction": "down"})

    data = client.get("/api/todos").json()["data"]
    assert [t["id"] for t in data] == ["b", "a", "c"]


def test_move_first_up_is_noop(client):
    _seed_three()

    resp = client.post("/api/todos/a/move", json={"direction": "up"})
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["data"]] == ["a", "b", "c"]


def test_move_last_down_is_noop(client):
    _seed_three()

    resp = client.post("/api/todos/c/move", json={"direction": "down"})
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["data"]] == ["a", "b", "c"]


def test_move_does_not_change_created_at(client):
    _seed("a", "A", created_at=1000)
    _seed("b", "B", created_at=1001)

    client.post("/api/todos/a/move", json={"direction": "down"})

    data = client.get("/api/todos").json()["data"]
    assert [t["id"] for t in data] == ["b", "a"]
    assert data[1]["createdAt"] == 1000


def test_move_unknown_id_returns_e1003(client):
    _seed_three()

    resp = client.post("/api/todos/does-not-exist/move", json={"direction": "up"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "E1003"


def test_move_invalid_direction_returns_e1004(client):
    _seed_three()

    resp = client.post("/api/todos/a/move", json={"direction": "left"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "E1004"
    assert body["message"] == "请求参数不合法"

    assert [t["id"] for t in client.get("/api/todos").json()["data"]] == ["a", "b", "c"]


def test_clear_completed_removes_completed_todos(client):
    _seed("a", "A", is_completed=True)
    _seed("b", "B", is_completed=False)
    _seed("c", "C", is_completed=True)

    resp = client.post("/api/todos/clear-completed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"] == {"removed": 2}

    data = client.get("/api/todos").json()["data"]
    assert [t["id"] for t in data] == ["b"]


def test_clear_completed_keeps_remaining_manual_order(client):
    _seed("a", "A")
    _seed("b", "B", is_completed=True)
    _seed("c", "C")
    _seed("d", "D", is_completed=True)

    client.post("/api/todos/clear-completed")

    data = client.get("/api/todos").json()["data"]
    assert [t["id"] for t in data] == ["a", "c"]


def test_clear_completed_when_none_completed_returns_zero(client):
    _seed("a", "A", is_completed=False)

    resp = client.post("/api/todos/clear-completed")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"removed": 0}

    assert len(client.get("/api/todos").json()["data"]) == 1


def test_clear_completed_on_empty_list_returns_zero(client):
    resp = client.post("/api/todos/clear-completed")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "data": {"removed": 0}}
