# Phase 4 — ExternalCrawler + Indexer + Research Bridge

> Phase 3 让 Curator 能从真实信号学习,Phase 4 给它新增第六类信号:**外部研究证据**。GitHub releases / arXiv 论文 / OpenReview 投稿被抓取、归一化、索引、按需检索,然后作为 `CuratorInput.external_findings` 接入 Phase 3 的现有管道 — 不绕过 candidate→validation→review。

## 1. 设计原则

| 原则 | 体现 |
|---|---|
| **不引入向量数据库** | 仅 SQLite FTS5 + simhash64,与 Phase 2 SkillRepo 同源算法 |
| **零真实外网测试依赖** | 三个 connector 都通过注入的 `HttpFetcher` Protocol 测试,`StubFetcher` 离线运行 |
| **External findings 不直接写 skill** | ResearchBridge 只产出 `ResearchFinding`,经过 `to_curator_signals()` 进入 `CuratorInput`,**Curator 仍是唯一提案者** |
| **三层去重** | canonical URL → sha256(body) → simhash64,各司其职 |
| **per-host rate limit** | UrllibFetcher 默认对 `export.arxiv.org` 强制 3 秒间隔(arXiv API ToU) |

## 2. 模块布局

```
stable_agent/
├── external_crawler/                 新增
│   ├── __init__.py            — 公共 API
│   ├── fetcher.py             — HttpFetcher Protocol + Urllib/Stub 实现
│   ├── models.py              — ExternalArtifact / IndexChunk / ResearchFinding
│   ├── normalizers.py         — canonicalize_url + collapse_whitespace
│   ├── arxiv_connector.py     — arXiv API + Atom XML 解析
│   ├── github_connector.py    — REST API: releases + readme
│   └── openreview_connector.py — API v2: notes/search
├── indexer/                          新增
│   ├── __init__.py
│   └── fts_store.py           — SQLite FTS5 + 双层去重
└── research_bridge/                  新增
    ├── __init__.py
    └── service.py             — chunk_markdown + RepoGap + ResearchBridge
```

## 3. 数据流

```
   GitHub / arXiv / OpenReview
           │
           │ HttpFetcher.get()
           ▼
   ExternalArtifact  ──────────┐
           │                   │
           ▼                   │
   chunk_markdown()            │
           │                   │
           ▼                   ▼
   IndexChunk[]    ──────▶ FtsStore (SQLite FTS5)
                                │
                                │ search(query)
                                ▼
                         BM25-ranked chunks
                                │
                                ▼
   ResearchBridge.find(RepoGap)
                                │
                                ▼
                         ResearchFinding[]
                                │
                                │ .to_curator_signals()
                                ▼
                  CuratorInput.external_findings
                                │
                                ▼
                  CuratorService.evaluate()
                                │
                                ▼
                  candidate skill (Phase 3)
```

**关键不变量**:Bridge 没有 SkillRepo 引用 — 测试通过 `not hasattr(bridge, "_repo")` 守护。

## 4. Connector 矩阵

| Connector | 端点 | 数据形态 | 信任分 |
|---|---|---|---:|
| `ArxivConnector` | `https://export.arxiv.org/api/query` | Atom XML | 0.85 |
| `GitHubConnector.list_releases` | `/repos/{o}/{r}/releases` | JSON | 0.7 |
| `GitHubConnector.fetch_readme` | `/repos/{o}/{r}/readme` | Markdown(raw) | 0.6 |
| `OpenReviewConnector` | `https://api2.openreview.net/notes/search` | JSON(v2 wrap+bare 兼容) | 0.75 |

**遵循的官方约束**:

- arXiv:`UrllibFetcher` 默认对 `export.arxiv.org` 串行间隔 ≥ 3s
- GitHub:支持可选 PAT `Authorization: Bearer ...`,默认无 token 跑公共 endpoint
- OpenReview:用 API v2(`api2.openreview.net`),v1 仅作历史兼容时使用 — Phase 4 不实现 v1
- GitHub Contents API 1000 文件上限 / 大仓库递归走 Trees API 的建议 — Phase 4 暂不实现 Trees API,只用 releases + readme(roadmap §3.2 显式范围),Phase 6 再扩

## 5. URL 归一化规则

`canonicalize_url` 把以下变体折成同一 canonical:

| 输入 | canonical |
|---|---|
| `HTTPS://Arxiv.org/abs/2401.12345v3?utm_source=tw` | `https://arxiv.org/abs/2401.12345` |
| `https://arxiv.org/pdf/2401.12345v2.pdf` | `https://arxiv.org/abs/2401.12345` |
| `https://github.com/foo/bar/` | `https://github.com/foo/bar` |
| `http://example.com/page#fragment` | `https://example.com/page` |
| `javascript:alert(1)` | `""`(拒绝) |

被剥离的 tracking 参数:`utm_source` / `utm_medium` / `utm_campaign` / `utm_term` / `utm_content` / `ref` / `ref_src` / `ab` / `context`。

## 6. SQLite 索引

`stable_agent/indexer/fts_store.py:SCHEMA_SQL` — 与 SkillRepo 完全分库:

```sql
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    source_type TEXT, canonical_url TEXT, ...
    sha256 TEXT,
    UNIQUE (canonical_url),
    UNIQUE (sha256)            -- cross-URL 同内容拒绝
);

CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    artifact_id TEXT REFERENCES artifacts ON DELETE CASCADE,
    text, code_snippet, language, simhash64_hex
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id, artifact_id, section_title, text, code_snippet, path_hint
);
```

**`_build_fts_match` 的两个安全设计**:
- 用 `[A-Za-z0-9_]{2,}` 切词,把 `held-out` 拆成 `["held","out"]`,避免 FTS5 把 `-` 解释成 NOT
- 每个 token 单独双引号包裹,防止用户传入的 `"` 操控 FTS5 boolean
- token 间用 `OR` 连接(而非 FTS5 默认的 AND),让"部分命中也参与 BM25 排序" — 否则一旦某关键词不在 chunk 里整条结果就消失

## 7. 测试矩阵(27 测试)

| 文件 | 测试数 | 角度 |
|---|---:|---|
| `test_external_crawler_connectors.py` | 13 | 三个 connector 的 fixture 解析;canonical URL 7 个变体;malformed XML 容错;invalid GitHub slug |
| `test_indexer_bm25_and_dedupe.py` | 14 | FTS upsert/get;canonical URL 去重;BM25 排序正确;sha256 + simhash 双层去重;chunk_markdown(代码栅栏单独成 chunk);ResearchBridge.find/.to_curator_signals;**Bridge 不持有 SkillRepo 引用**(invariant) |

## 8. 关键不变量(测试守护)

| 不变量 | 测试 |
|---|---|
| **Bridge 不写 skill** | `test_research_bridge_does_not_modify_skills` |
| **BM25 排序正确** | `test_fts_store_search_returns_bm25_ranked` |
| **canonical_url 折叠 7 种变体** | `test_canonicalize_url_collapses_known_variants` |
| **arXiv 版本号 v3 → 去版本** | URL canonical 测试 + arxiv connector 测试同时校验 |
| **代码栅栏单独成 chunk** | `test_chunk_markdown_extracts_code_fences_separately` |
| **simhash 近邻识别** | `test_fts_store_finds_near_duplicate_by_simhash` |
| **sha256 cross-URL 去重** | `test_fts_store_finds_exact_duplicate_by_sha256` |

## 9. Curator 接入示例

```python
from stable_agent.research_bridge import ResearchBridge, RepoGap
from stable_agent.indexer import FtsStore
from stable_agent.external_crawler import ArxivConnector, UrllibFetcher
from stable_agent.core.curator_service import CuratorService, CuratorInput

# 一次性索引(可定时跑)
store = FtsStore("data/external_index.sqlite")
bridge = ResearchBridge(store)
arxiv = ArxivConnector(UrllibFetcher())
for art in arxiv.search("skill curation held-out validation", max_results=10):
    bridge.index_artifact(art, body=art.raw_metadata.get("summary", ""))

# 在 Curator 评估前查相关证据
gap = RepoGap(failure_mode="missing_validation", keywords=("held-out","skill"))
findings = bridge.find(gap)
external_signals = ResearchBridge.to_curator_signals(findings)

# 注入 CuratorInput
curator = CuratorService(repo)
decision = curator.evaluate(CuratorInput(
    run_id="run_xxx",
    task_input="...",
    eval_score=0.42,
    eval_passed=False,
    external_findings=external_signals,   # ← Phase 4 接入点
))
```

## 10. PR 验收清单

- [x] 三类 connector 可在 fixture 下运行(`StubFetcher`)
- [x] FTS / BM25 检索可用 + token-AND/OR 安全处理
- [x] dedupe 可测(canonical_url 唯一 / sha256 唯一 / simhash 近邻)
- [x] findings 能进入 curator / validator 输入(`to_curator_signals` API + 单测)
- [x] 测试中不依赖真实外网
- [x] 不引入独立向量 DB
- [x] 不直接 promote external findings 为 skill

## 11. 已知遗留(交给 Phase 5-6)

| # | 项 | 处置 |
|---|---|---|
| L1 | `find_duplicates` 仍是全表扫描 | Phase 6:加 LSH bucket(simhash 前 16 bit 分桶) |
| L2 | GitHub Trees API 没接 — 仅支持 releases + readme | Phase 6 follow-up,roadmap §3.2 |
| L3 | OpenReview v1 不支持 | 非目标(2024 之前会议很少需要) |
| L4 | `_freshness_score` 简化版 — 只用日期段映射 | Phase 5 + Observer 接入后再 tune |
| L5 | 没有 ACL Anthology / NeurIPS HTML fallback | 路线图说"有 API 就用,没就 HTML metadata parser" — Phase 6 单独跟进 |
| L6 | 索引刷新调度(crontab / harness research)Phase 6 Harness CLI 才有 | — |
