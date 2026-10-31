# FastAPI TodoList 实现计划

## Repository Research

- 已有 [SPEC.md](../../SPEC.md)（v2.0，FastAPI 版）与 [AGENTS.md](../../AGENTS.md) 两份约束文档。
- 当前工作区仅有 `SPEC.md`、`AGENTS.md`、`.git/`，无任何代码文件，属于从零实现。
- 硬约束：代码结构 `main.py` + `templates/index.html`（CSS/JS 内联），无前端框架、无 CDN、无数据库、内存存储、`uvicorn main:app --reload`。
- 业务功能必须 1:1 对齐 SPEC：增删改查、模糊搜索、状态筛选、4 种排序、上移/下移手动排序、行内编辑、清空已完成；错误码 `E1001`/`E1002`/`E1003`/`E1004` 含义与 HTTP 状态码映射不变。

## Files and Modules

| 文件 | 状态 | 职责 |
|---|---|---|
| `requirements.txt` | 新增 | 依赖：`fastapi`、`uvicorn`、`jinja2`、`httpx`、`pytest` |
| `main.py` | 新增 | FastAPI 应用；Pydantic 数据模型；内存 `TODOS` 列表与 `threading.Lock`；`validate_text()`；6 个 REST 接口；`GET /` 渲染 `index.html`；统一 `err()` 错误响应 |
| `templates/index.html` | 新增 | Jinja2 页面骨架（标题、输入区、工具条、列表容器）+ 内联 CSS + 内联 JS（`fetch` 调用接口、`textContent` 渲染、200ms 防抖搜索、行内编辑、上移/下移、清空已完成、错误提示条） |
| `tests/conftest.py` | 新增 | `TestClient(app)` fixture；每个测试前清空内存 `TODOS` |
| `tests/test_api.py` | 新增 | 覆盖全部接口与错误码的 pytest 用例，TDD 测试先行 |

> 不在本次新增：`static/`、`app.py`、数据库迁移、前端构建产物。

## 接口清单

| 方法 | 路径 | 入参 | 成功响应 |
|---|---|---|---|
| GET | `/` | — | 200 `text/html` |
| GET | `/api/todos` | query: `query`(默认 "")、`filter`(`all`\|`incomplete`\|`completed`，默认 `all`)、`sort`(`manual`\|`createdDesc`\|`createdAsc`\|`incompleteFirst`，默认 `manual`) | 200 `{ok:true,data:Todo[]}` |
| POST | `/api/todos` | `{text:string}` | 201 `{ok:true,data:Todo}` |
| PATCH | `/api/todos/{id}` | `{text?:string, isCompleted?:boolean}`（至少一项） | 200 `{ok:true,data:Todo}` |
| DELETE | `/api/todos/{id}` | — | 200 `{ok:true,data:true}` |
| POST | `/api/todos/{id}/move` | `{direction:"up"\|"down"}` | 200 `{ok:true,data:Todo[]}` |
| POST | `/api/todos/clear-completed` | — | 200 `{ok:true,data:{removed:N}}` |

### 错误码与 HTTP 映射

| 错误码 | HTTP | 触发条件 |
|---|---|---|
| `E1001` | 400 | trim 后长度为 0，或 `text` 缺失/非字符串 |
| `E1002` | 400 | trim 后长度 > 100 |
| `E1003` | 404 | 操作目标 `id` 不存在 |
| `E1004` | 400 | 请求体字段类型非法（`isCompleted` 非布尔、`direction` 非法、PATCH 无任何可改字段） |

> `filter`/`sort` 未知取值按默认值处理，不报错。

## 数据结构

### Todo（接口 JSON，camelCase）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | UUID v4，服务端生成 |
| `text` | string | trim 后 1~100 字符 |
| `isCompleted` | boolean | 完成状态 |
| `createdAt` | number | 创建时间戳 ms |
| `updatedAt` | number | 最近修改时间戳 ms |

- Python 内部 snake_case，Pydantic `Field(alias=...)` + `model_config(populate_by_name=True)`，响应 `model_dump(by_alias=True)`。
- 内存存储：模块级 `TODOS: list[Todo]`，数组顺序即手动排序顺序；不持久化，重启清空。
- 单进程单 worker 运行，写操作用 `threading.Lock` 保护。

## Implementation Steps（小步快跑 + TDD）

### 阶段 1：项目骨架与首页
- 改动：创建 `requirements.txt`、`main.py`（仅 `GET /`）、`templates/index.html`（仅标题占位）。
- 测试要点：`GET /` 返回 200 且 Content-Type 含 `text/html`。
- 验收：`pytest tests/test_api.py::test_home_returns_200` 通过；浏览器访问可见页面。

### 阶段 2：数据模型 + `GET /api/todos`（筛选/搜索/排序）
- 改动：`Todo` 模型、`TODOS=[]`、`lock`、`GET /api/todos` 实现 4 种排序与 filter/search。
- 测试要点：
  - `sort=createdDesc`/`createdAsc`/`incompleteFirst` 顺序正确
  - `filter=completed`/`incomplete` 过滤正确
  - `query=关键字` 不区分大小写模糊匹配
  - 非法 `sort`/`filter` 回退默认值
- 验收：对应 pytest 全绿。

### 阶段 3：`POST /api/todos`（添加 + `E1001`/`E1002`）
- 改动：`validate_text()`、`POST` 入库（trim、UUID、时间戳）。
- 测试要点：
  - 合法 → 201，`data.text` 为 trim 后值，`isCompleted=False`
  - 空串/纯空格 → 400 `E1001`
  - 101 字符 → 400 `E1002`
  - 100 字符 → 201
- 验收：pytest 全绿。

### 阶段 4：`PATCH /api/todos/{id}`（编辑 + 完成切换 + 三错误码）
- 改动：部分更新 `text`/`isCompleted`，更新 `updatedAt`。
- 测试要点：
  - 更新文本 / 切换完成状态成功
  - 空文本 → 400 `E1001`；超长 → 400 `E1002`
  - 不存在 `id` → 404 `E1003`
  - 无字段 / 类型非法 → 400 `E1004`
- 验收：pytest 全绿。

### 阶段 5：`DELETE /api/todos/{id}` + `E1003`
- 改动：从列表移除指定项。
- 测试要点：删除存在 → 200 `true`；删除不存在 → 404 `E1003`。
- 验收：pytest 全绿。

### 阶段 6：`POST /api/todos/{id}/move`（上移/下移 + 边界 + `E1003`）
- 改动：调整 `TODOS` 顺序；首项不可上移、末项不可下移（返回当前顺序，200）。
- 测试要点：
  - `down`/`up` 正确交换
  - 首项 `up` / 末项 `down` → 顺序不变，200
  - 不存在 `id` → 404 `E1003`
  - `direction` 非法 → 400 `E1004`
- 验收：pytest 全绿。

### 阶段 7：`POST /api/todos/clear-completed`
- 改动：移除全部已完成任务，返回 `removed` 数量。
- 测试要点：2 条已完成 → `removed:2`，剩 1 条；无已完成 → `removed:0`。
- 验收：pytest 全绿。

### 阶段 8：前端模板 `templates/index.html` 完整实现
- 改动：补全 UI 与 JS —— 添加/搜索/筛选/排序控件；`fetch` 调用接口；`textContent` 渲染列表；200ms 防抖搜索；行内编辑（Enter 保存/Esc 取消/失焦保存）；上移/下移按钮（非 manual 模式隐藏）；清空已完成（`confirm`）；错误提示条。
- 测试要点：无 pytest，按 SPEC §8.1 正常用例 N-1~N-8 与 §8.2 边界用例人工/HTTP 回归。
- 验收：所有 N/B 用例符合预期；刷新页面数据不丢（服务未重启）。

### 阶段 9：整体验收
- 改动：无代码改动。
- 测试要点：完整跑 SPEC §8 的 N/B/E 用例；E-1~E-5 用 `fetch`/`curl` 断言状态码与错误码；重启 `uvicorn` 后 `GET /api/todos` 返回 `[]`。
- 验收：全部通过。

## Dependencies and Considerations

- Python 3.10+；FastAPI + uvicorn + Jinja2（均为 AGENTS.md 规定）。
- 运行强制单 worker（`uvicorn main:app --reload` 默认），不使用 `--workers > 1`，否则多进程内存不一致。
- `sort != manual` 时只生成新列表返回，**不写回** `TODOS`，避免破坏手动顺序。
- 前端不持有持久化数据；每次写操作成功后统一调用 `loadTodos()`（携带当前 query/filter/sort）重渲染。
- 搜索防抖内维护 `requestSeq`，仅渲染最后一次请求结果，避免竞态。
- `clear-completed` 的「N」取自最近一次列表查询的全量已完成计数。

## Validation

- 阶段 1-7：`pytest tests/test_api.py -v`，断言 HTTP 状态码与 JSON 完全匹配 SPEC §5。
- 阶段 8：浏览器按 N-1~N-8 操作，观察 UI 反馈与数据持久。
- 阶段 9：`fetch`/`curl` 验证 E-1~E-5；重启服务验证无持久化。

## Risks

- **并发竞态**：uvicorn 线程池下写操作可能同时修改 `TODOS`。→ 所有写操作加 `threading.Lock`；明确单 worker。
- **Pydantic v2 字段别名**：默认 `model_dump()` 返回 snake_case，破坏 camelCase 约定。→ `model_config(populate_by_name=True)` + 响应统一 `model_dump(by_alias=True)`。
- **手动顺序被排序覆盖**：时间排序若写回内存会打乱手动顺序。→ 非 `manual` 排序只在响应层生成新列表，不修改 `TODOS`。
- **前端 XSS**：用户文本注入 HTML。→ 严格 `textContent`；服务端 Jinja2 默认 autoescape；禁止拼接 `innerHTML`。
- **防抖搜索结果错乱**：用户快速输入/清空导致旧请求后返回。→ `requestSeq` 序号比对，仅渲染最后一次响应。
- **`confirm` 自动化阻塞**：无头测试无法交互。→ `confirm` 仅在阶段 8/9 人工验证；接口层不依赖弹窗。
- **`maxlength` 与 trim 计数冲突**：UI 无法输入 >100 字符。→ 接口层保留 `validate_text()` >100 校验，异常用例通过接口调用验证（已在 SPEC 中确认）。
