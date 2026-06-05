# Phase 5 — Observer 证据控制台

> Phase 0–4 都是后端能力,Phase 5 让这些能力**对用户可见**:把 Phase 0 的 13 必需事件、Phase 3 的 ValidationReport、Phase 4 的 research findings 全部聚合成 Run Detail / Impact / Compare 三张证据视图。

## 1. 设计原则

| 原则 | 体现 |
|---|---|
| **不破坏既有 Dashboard** | Phase 5 加 `/api/runs/{run_id}/detail`(注意 ``/detail`` 后缀,不同于 SaaS 的 ``/api/runs/{id}``);旧路由保持不变 |
| **completed run 永不显示 0%** | `run_detail_api._summarize_run` 显式覆盖:`is_completed=True ⇒ progress_pct=100`,Phase 5 prompt invariant |
| **数据驱动,无前端编造** | 三个 API 全部基于 `RunStore` + `ValidationReportStore` 真实事件 |
| **CLI / LocalRuntime 可用** | 不依赖 SaaS,任何 RunStore-have 的部署都能跑 |
| **JSON payload 受控** | `_shrink_event` 限制每个 event 的输出 keys,防 MB 级 JSON |

## 2. 模块布局

```
stable_agent/api/                      新增
├── __init__.py            — re-export build_*_router / ValidationReportStore
├── run_detail_api.py      — GET /api/runs/{run_id}/detail
├── impact_api.py          — GET /api/runs/{run_id}/impact
├── compare_api.py         — GET /api/runs/{run_id}/compare
│                            GET /api/validations/{validation_id}
└── validation_store.py    — ValidationReportStore (JSON-on-disk)
```

> **命名澄清**:`stable_agent/api/` 之前不存在(Phase 0 audit §1 列过的目录里没它),Phase 5 全新建立。与 `web/routes/` 的 SaaS 路由是平行关系 — Phase 5 路由用 `APIRouter` factory,允许任意 FastAPI app 通过 `app.include_router(...)` 挂载。

## 3. ValidationReport 持久化

Phase 3 产出 `ValidationReport` 但**不落盘**;Phase 5 通过 `ValidationReportStore` 修复:

```
{root}/data/validations/
├── val_<id>.json
└── ...
```

每个 JSON 文件:
```json
{
  "validation_id": "val_xxxxxxxxxxxx",
  "run_id": "run_yyyyyyyyyyyy",
  "saved_at": "2026-06-05T...",
  "report": { ...ValidationReport.to_dict()... }
}
```

`validation_id` 严格匹配 `[A-Za-z0-9_-]{1,64}` — 路径遍历守护(`..%2Fetc%2Fpasswd` 被拒,见 `test_compare_api_rejects_invalid_validation_id`)。

## 4. API 端点

| 方法 | 路径 | 用途 | 主要字段 |
|---|---|---|---|
| GET | `/api/runs/{run_id}/detail` | 单 run 概览 | `is_completed` / `progress_pct` / `missing_required_events` / `event_sync_ok` / `eval_score` |
| GET | `/api/runs/{run_id}/impact` | 这次 run 改了什么 | `memory_hits` / `skill_hits` / `learning_timeline` / `token_impact` / `required_event_completeness` |
| GET | `/api/runs/{run_id}/compare` | 该 run 的最新 A/B 报告 | `candidate_skill_id` / `avg_score_delta` / `regression_rate` / `cases[]` |
| GET | `/api/validations/{validation_id}` | 一份具体的 ValidationReport | 同 compare |

事件白名单(决定哪些事件进入 impact/compare 视图):

```python
MEMORY_EVENT_TYPES = (
    "temporal_memory.retrieved", "memory.update.candidate",
    "memory.review.completed",
)
SKILL_EVENT_TYPES = (
    "skill.candidate.created", "skill.patch.proposed",
    "skill.validated", "skill.promoted", "skill.exported",
)
LEARNING_EVENT_TYPES = (
    "regression.generated", "skill.candidate.created",
    "skill.patch.proposed", "validation.checked",
    "human_review.required", "human_review.completed",
)
```

## 5. 关键不变量(测试守护)

| 不变量 | 测试 |
|---|---|
| **completed run 不返 0%** | `test_run_detail_completed_run_reports_full_progress` |
| **partial run 精确列出缺失事件** | `test_run_detail_partial_run_reports_missing_events`(11/13 缺失) |
| **未知 run → 404** | `test_run_detail_unknown_run_returns_404` |
| **token_impact 缺失时返 None,不崩** | `test_impact_report_token_impact_falls_back_when_missing` |
| **`_shrink_event` 限制 payload** | `test_impact_report_collects_memory_and_skill_hits` |
| **ValidationReport 圆环 round-trip** | `test_validation_store_round_trip` |
| **路径遍历 validation_id 拒绝** | `test_validation_store_rejects_traversal_id` |
| **没有 validation 报告 → 404** | `test_compare_api_404_when_run_has_no_report` |

## 6. 测试矩阵(14 测试)

| 文件 | 测试数 | 角度 |
|---|---:|---|
| `test_observer_impact_compare.py` | 14 | run_detail / impact / compare 三 API + ValidationReportStore;TestClient e2e + 纯函数单元 |

## 7. 接入示例(FastAPI app)

```python
from fastapi import FastAPI
from stable_agent.observation.run_store import RunStore
from stable_agent.api import (
    build_run_detail_router, build_impact_router,
    build_compare_router, ValidationReportStore,
)

app = FastAPI()
run_store = RunStore()
validation_store = ValidationReportStore(root=".")

app.include_router(build_run_detail_router(run_store=run_store))
app.include_router(build_impact_router(run_store=run_store))
app.include_router(build_compare_router(validation_store=validation_store))
```

CLI 用户(无 web)直接用:

```python
from stable_agent.api.impact_api import build_impact_report
events = run_store.get_events("run_xxx")
print(build_impact_report("run_xxx", events))
```

## 8. PR 验收清单

- [x] memory / skill / validation / impact 全部可视化(JSON API)
- [x] replay API 驱动页面(全部读 `RunStore`/`ValidationReportStore`,无前端编造)
- [x] **completed run 不再显示 0%** — Phase 5 prompt 硬约束
- [x] 不破坏现有 Dashboard run detail(SaaS `/api/runs/{id}` 保留)
- [x] 不显示模型隐藏 chain-of-thought(`_shrink_event` 限制 keys)
- [x] 不依赖 SaaS — CLI / LocalRuntime 可用

## 9. 已知遗留(交给 Phase 6)

| # | 项 | 处置 |
|---|---|---|
| L1 | 没有 HTML 模板 — 只暴露 JSON API | Phase 6 Harness CI 在 `web/templates/run_observer.html` 加最小 console;Phase 5 优先 backend correctness |
| L2 | `Validator` 还没把 `ValidationReport` 自动落到 `ValidationReportStore` | Phase 6 wiring:`stable_agent/harness/validate.py` 显式调用 `store.save()` |
| L3 | `find_related` impact_api 没接 research_bridge findings | Phase 6 可加 `research_findings` 字段到 ImpactReport |
| L4 | Compare API 只支持 latest;历史比较走 `list_all` 自取 | Phase 6 加 `?limit=N` 参数 |
