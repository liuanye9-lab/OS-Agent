"""RejectedEditBuffer 单元测试。

测试被拒绝编辑的添加、加载、相似度检测和持久化功能。
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stable_agent.skill_optimizer.models import (
    SkillEdit,
    ValidationResult,
)
from stable_agent.skill_optimizer.rejected_edit_buffer import RejectedEditBuffer
from stable_agent.skill_optimizer.edit_models import BoundedSkillEdit
from stable_agent.skill_optimizer.rejected_buffer import RejectedBuffer


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def tmp_buffer_path():
    """创建临时 JSONL 文件路径。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "rejected_edits.jsonl"


@pytest.fixture
def buffer_instance(tmp_buffer_path):
    """创建 RejectedEditBuffer 实例。"""
    return RejectedEditBuffer(buffer_path=str(tmp_buffer_path))


@pytest.fixture
def sample_validation_result():
    """创建测试用 ValidationResult。"""
    return ValidationResult(
        candidate_skill_version="v1.1",
        baseline_skill_version="v1.0",
        baseline_score=0.80,
        candidate_score=0.75,
        passed=False,
        score_delta=-0.05,
        explanation="候选版本评分低于基线，包含回归用例。",
    )


# ============================================================================
# Helpers
# ============================================================================


def make_edit(
    edit_id: str = "e-1",
    op: str = "append",
    target: str | None = None,
    content: str | None = None,
    source_type: str = "failure",
    support_count: int = 0,
) -> SkillEdit:
    """创建测试用 SkillEdit。"""
    return SkillEdit(
        id=edit_id,
        op=op,
        target=target,
        content=content,
        source_type=source_type,
        support_count=support_count,
        created_at=datetime.now(),
    )


# ============================================================================
# Tests
# ============================================================================


class TestAddAndLoad:
    """测试添加和加载被拒绝编辑。"""

    def test_add_and_load_rejected(self, buffer_instance, sample_validation_result):
        """添加被拒绝编辑后可以通过 load_recent 加载。"""
        edits = [
            make_edit("e1", op="replace", target="old", content="new"),
            make_edit("e2", op="append", content="Extra section"),
        ]

        buffer_instance.add_rejected(edits, sample_validation_result)
        loaded = buffer_instance.load_recent()

        assert len(loaded) == 2
        # 验证编辑内容被保留
        assert loaded[0].id == "e1"
        assert loaded[0].op == "replace"
        assert loaded[0].target == "old"
        assert loaded[1].id == "e2"

    def test_add_rejected_empty_list(self, buffer_instance, sample_validation_result):
        """空编辑列表不写入文件。"""
        buffer_instance.add_rejected([], sample_validation_result)
        loaded = buffer_instance.load_recent()
        assert len(loaded) == 0

    def test_load_recent_empty_buffer(self, buffer_instance):
        """空缓冲区返回空列表。"""
        loaded = buffer_instance.load_recent()
        assert len(loaded) == 0

    def test_load_recent_limit(self, buffer_instance, sample_validation_result):
        """load_recent 遵守 limit 参数。"""
        edits = [
            make_edit(f"e{i}", op="append", content=f"Content {i}")
            for i in range(10)
        ]
        buffer_instance.add_rejected(edits, sample_validation_result)

        limited = buffer_instance.load_recent(limit=5)
        assert len(limited) == 5

    def test_reason_from_validation_result(self, buffer_instance, sample_validation_result):
        """被拒绝编辑的 reason 来自 validation_result.explanation。"""
        edit = make_edit("e1", op="append", content="test")
        buffer_instance.add_rejected([edit], sample_validation_result)

        loaded = buffer_instance.load_recent()
        assert len(loaded) == 1
        assert "回归" in loaded[0].reason


class TestSimilarityDetection:
    """测试相似度检测。"""

    def test_is_similar_to_rejected_same_op_target(self, buffer_instance, sample_validation_result):
        """相同 op+target 的编辑被判定为相似。"""
        edit = make_edit("e1", op="replace", target="specific text", content="new")
        buffer_instance.add_rejected([edit], sample_validation_result)

        similar = make_edit("e2", op="replace", target="specific text", content="different")
        assert buffer_instance.is_similar_to_rejected(similar) is True

    def test_is_similar_to_rejected_append_content(self, buffer_instance, sample_validation_result):
        """append 操作且 content 相似度 > 0.7 时判定为相似。"""
        edit = make_edit(
            "e1",
            op="append",
            content="This is a very long content that should match the first 60 chars roughly",
        )
        buffer_instance.add_rejected([edit], sample_validation_result)

        similar = make_edit(
            "e2",
            op="append",
            content="This is a very long content that should match the first 60 chars roughly but different ending",
        )
        assert buffer_instance.is_similar_to_rejected(similar) is True

    def test_not_similar_to_different_edit(self, buffer_instance, sample_validation_result):
        """完全不同的编辑不被判定为相似。"""
        edit = make_edit("e1", op="replace", target="target A", content="content A")
        buffer_instance.add_rejected([edit], sample_validation_result)

        different = make_edit("e2", op="replace", target="target B", content="content B")
        assert buffer_instance.is_similar_to_rejected(different) is False

    def test_not_similar_different_op(self, buffer_instance, sample_validation_result):
        """不同 op 的编辑不被判定为相似（非 append 情况）。"""
        edit = make_edit("e1", op="replace", target="same", content="content")
        buffer_instance.add_rejected([edit], sample_validation_result)

        different_op = make_edit("e2", op="delete", target="same")
        assert buffer_instance.is_similar_to_rejected(different_op) is False

    def test_not_similar_append_different_content(self, buffer_instance, sample_validation_result):
        """append 操作但内容完全不同时不被判定为相似。"""
        edit = make_edit(
            "e1",
            op="append",
            content="AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH",
        )
        buffer_instance.add_rejected([edit], sample_validation_result)

        very_different = make_edit(
            "e2",
            op="append",
            content="ZZZZ YYYY XXXX WWWW VVVV UUUU TTTT SSSS",
        )
        assert buffer_instance.is_similar_to_rejected(very_different) is False


class TestPersistence:
    """测试 JSONL 持久化。"""

    def test_jsonl_persistence(self, tmp_path, sample_validation_result):
        """验证编辑持久化到 JSONL 文件并可重新加载。"""
        buffer_path = tmp_path / "test_rejected.jsonl"
        buffer_instance = RejectedEditBuffer(buffer_path=str(buffer_path))

        edits = [
            make_edit("e-jsonl-1", op="replace", target="t1", content="c1"),
            make_edit("e-jsonl-2", op="delete", target="t2"),
        ]
        buffer_instance.add_rejected(edits, sample_validation_result)

        # 验证文件存在且内容正确
        assert buffer_path.exists()

        lines = buffer_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            record = json.loads(line)
            assert "id" in record
            assert "op" in record
            assert "reason" in record

        # 重新加载验证
        loaded = buffer_instance.load_recent()
        assert len(loaded) == 2
        assert loaded[0].id == "e-jsonl-1"
        assert loaded[1].id == "e-jsonl-2"

    def test_jsonl_append_mode(self, tmp_path, sample_validation_result):
        """多次添加时使用追加模式，不覆盖已有数据。"""
        buffer_path = tmp_path / "test_append.jsonl"
        buffer_instance = RejectedEditBuffer(buffer_path=str(buffer_path))

        edits1 = [make_edit("e1", op="append", content="first")]
        edits2 = [make_edit("e2", op="append", content="second")]

        buffer_instance.add_rejected(edits1, sample_validation_result)
        buffer_instance.add_rejected(edits2, sample_validation_result)

        loaded = buffer_instance.load_recent()
        assert len(loaded) == 2


def test_recursive_rejected_buffer_prevents_repeat(tmp_path):
    buffer = RejectedBuffer(tmp_path / "recursive_rejected.jsonl")
    edit = BoundedSkillEdit(operation="ADD_RULE", target="Procedure", content="Run pytest first.")
    buffer.add(edit, "validation did not improve")

    assert buffer.is_repeat(BoundedSkillEdit(operation="ADD_RULE", target="Procedure", content="Run pytest first.")) is True


class TestClearBuffer:
    """测试清空缓冲区。"""

    def test_clear_buffer(self, buffer_instance, sample_validation_result):
        """clear() 删除 JSONL 文件，清空所有数据。"""
        edit = make_edit("e1", op="append", content="test")
        buffer_instance.add_rejected([edit], sample_validation_result)

        # 确认有数据
        assert len(buffer_instance.load_recent()) == 1

        # 清空
        buffer_instance.clear()
        assert len(buffer_instance.load_recent()) == 0
        assert not buffer_instance.buffer_path.exists()

    def test_clear_empty_buffer(self, buffer_instance):
        """清空空缓冲区不报错。"""
        buffer_instance.clear()  # 不应抛出异常
        assert len(buffer_instance.load_recent()) == 0


class TestBufferPathCreation:
    """测试路径创建。"""

    def test_buffer_creates_directory(self, tmp_path):
        """初始化时自动创建目录。"""
        nested_path = tmp_path / "a" / "b" / "rejected.jsonl"
        buffer_instance = RejectedEditBuffer(buffer_path=str(nested_path))
        assert nested_path.parent.exists()
