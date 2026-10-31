# 项目概述

网页版 TodoList，FastAPI + Jinja2 模板，内存存储任务，实现任务增删改查、模糊搜索、筛选、4 种排序、上移下移手动排序、行内编辑、清空已完成，为个性化扩展需求。

# 技术约束

- Python FastAPI，uvicorn 启动
- 前端 Jinja2 渲染 HTML，原生 JS，无前端框架
- 数据存在后端内存，服务重启数据清空，不使用数据库

# 开发约定

1. 严格依照 SPEC.md 需求规格开发，不擅自增减功能
2. 代码结构：main.py + templates/index.html

# 运行命令

- 安装依赖：`pip install fastapi uvicorn jinja2`
- 启动服务：`uvicorn main:app --reload`
- 访问地址：http://127.0.0.1:8000
