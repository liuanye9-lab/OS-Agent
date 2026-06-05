# Phase 2 — SkillRepo v2

> 文件 + SQLite FTS5 + 双层签名去重的外部 skill 仓。Phase 2 不实现自动 promote,只把生命周期骨架立起来,让 Phase 3 Curator/Validator 有真实的 candidate 落地点。

## 1. 设计原则

| 原则 | 体现 |
|---|---|
| **不与 V4 `skill_optimizer` 冲突** | 新 repo 在空目录 `stable_agent/skills/`(原 V4 仍在 `stable_agent/skill_optimizer/`) |
| **`best_skill.md` 是导出,不是源** | candidate 写入**永不**触碰 `best_skill.md`;只有 `export_best_skill()` 写它 |
| **promoted-only 检索** | `search()` 默认 `status='promoted'`;非 promoted skill 必须显式 `include_all_statuses=True` |
| **no auto-promote** | Phase 2 只暴露 `transition_status`,不做"自动 candidate→promoted" |
| **不引入新依赖** | 仅用 stdlib + 已有 PyYAML |

## 2. 模块布局

```
stable_agent/skills/
├── __init__.py        — 公共 API re-export
├── models.py          — SkillStatus / SkillFrontmatter / SkillDocument
├── signature.py       — sha256 + simhash64 + canonicalize
├── lifecycle.py       — LEGAL_TRANSITIONS + transition()
├── index_store.py     — SQLite FTS5 索引
└── repository.py      — 文件 + 索引编排;best_skill.md 导出
```

## 3. 数据模型

### SkillDocument(frozen)

```python
@dataclass(frozen=True)
class SkillDocument:
    frontmatter: SkillFrontmatter
    sections: dict[str, str]        # "Intent"/"Procedure"/...
```

### SkillStatus 与转换

```
draft ─┬─→ candidate ─┬─→ validated ─┬─→ promoted ─→ deprecated ─→ archived
       │              │              │                  ↑
       │              │              │                  └──── (rare un-deprecate)
       └──→ rejected ←┴── rejected   └──→ rejected
```

非法跳变(例:`draft → promoted`)抛 `SkillTransitionError`。

### Markdown + frontmatter 形状

```markdown
---
skill_id: sk_context_guard_v3
version: 3
status: candidate
domain: coding
owner: curator_v1
retrieval_tags: [context, compression]
task_types: [coding_task]
triggers:
  must_contain: ["上下文"]
  should_contain: ["压缩"]
  must_avoid: ["闲聊"]
metrics:
  validations: 1
  win_rate: 1.0
  avg_token_delta: -0.11
  last_validation_score: 0.82
source_runs: ["run_xxx"]
risk_level: low
signature_sha256: "..."
simhash64: "..."             # 16 hex chars
---

# Intent
# Procedure
# Guardrails
# Positive examples
# Negative examples
# Patch history
```

## 4. 双层签名去重

| 层 | 算法 | 用途 |
|---|---|---|
| **strict** | `sha256(canonicalize(intent + procedure + guardrails + sorted(tags)))` | UNIQUE 约束,跨 skill 撞签名 → `DuplicateSkillError` |
| **near** | `simhash64`(本地实现,blake2b 8-byte token hash + 64 位累加器) | `find_near_duplicates(threshold=3)` 默认值,Hamming 距离阈值 |

**canonical 规则**:
1. 每段内部空白合并为单空格
2. 段间用 sentinel `\n---\n` 拼接(位置敏感 — 顺序变化 = 签名变化,故意如此设计防止 tag 互换误判)
3. tags 小写、去空、去重、排序、逗号拼接

## 5. SQLite 索引

```sql
CREATE TABLE skills (
    skill_id TEXT, version INTEGER, status TEXT,
    domain TEXT, owner TEXT, risk_level TEXT,
    retrieval_tags TEXT, task_types TEXT,
    validations INTEGER, win_rate REAL,
    avg_token_delta REAL, avg_latency_delta REAL,
    last_validation_score REAL,
    content_signature_sha256 TEXT NOT NULL,
    simhash64_hex TEXT,
    file_path TEXT,
    created_at TEXT, updated_at TEXT,
    PRIMARY KEY (skill_id, version),
    UNIQUE (content_signature_sha256)
);

CREATE VIRTUAL TABLE skills_fts USING fts5(
    skill_id, version, intent, procedure, guardrails, tags
);
```

> Phase 2 只用 SQLite FTS5(内置于 stdlib `sqlite3` ≥ 3.9 + Python 3.11+),不引入向量数据库 — 路线图 Phase 4 一直到 Phase 6 都不需要 vector retrieval,简单 BM25 + simhash 就够。

## 6. `best_skill.md` 行为

- **candidate 写入** → 永不写 `best_skill.md`
- `export_best_skill()` → 收集所有 `status=promoted` 的最新版本,合并写到 `best_skill.md`(每 skill 一段,带 `<!-- skill_repo_v2: derived export — do not edit by hand -->` 头)
- 没有 promoted skill → 写 stub `<!-- skill_repo_v2: no promoted skills -->`(覆盖式,确保旧的 promoted 内容会失效)

## 7. 测试矩阵(30 测试)

| 文件 | 用途 | 关键断言 |
|---|---|---|
| `test_skill_signature_and_duplicate.py` | 签名层 | canonical 对空白/tag 顺序不敏感,但**对段位置敏感**;simhash64 近邻;hex 双向往返;repo 跨 skill 拒重 |
| `test_skill_repo_v2.py` | 文件 + 索引 | 圆环 round-trip;FTS 默认 promoted-only;legal/illegal 转换;**candidate 写入不触碰 `best_skill.md`** |

## 8. PR 验收清单

- [x] skill schema 固定(YAML frontmatter + H1 sections)
- [x] 文件 + SQLite 双层可用
- [x] duplicate detection 可测(strict + near)
- [x] promoted skill 才进入主检索(默认 search)
- [x] 不自动覆盖 `best_skill.md`
- [x] 不让 candidate 默认进入主检索
- [x] 不引入独立向量数据库

## 9. Phase 3 衔接点

Phase 2 留好的接入面:

- `Curator.propose(trace, eval, feedback) → SkillDocument(status=draft)`
  → 调 `repo.write(skill)` → 调 `repo.transition_status(skill_id, v, CANDIDATE)`
- `Validator.validate(candidate, related_tasks)` 通过后
  → 调 `repo.transition_status(skill_id, v, VALIDATED)`
- `HumanReview.approve(skill)` 通过后
  → 调 `repo.transition_status(skill_id, v, PROMOTED)`
  → 调 `repo.export_best_skill()`(可选,如果保留旧 consumer)

## 10. 已知遗留(交给 Phase 3+)

| # | 项 | 处置 |
|---|---|---|
| L1 | `find_near_duplicates` 全表扫描 → ~10⁴ skill 时退化 | Phase 5+ 加 LSH bucket |
| L2 | 路线图建议的 BM25 ≥ 0.78 / Jaccard ≥ 0.6 阈值未实现 | Phase 3 Curator 决定阈值后再加 |
| L3 | `merge` 候选(simhash hit + score delta 大)未实现 | Phase 3 Curator 责任 |
| L4 | 旧 `skills/best_skill.md` 由 V4 流程写入 | Phase 6 切到 V2 export 后再清理 |
