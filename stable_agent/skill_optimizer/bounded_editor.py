"""SkillOpt-style bounded skill editor.

The editor intentionally supports only a tiny edit language. It rejects whole
document rewrites, deletion by default, safety/human-review section removal,
and edits that do not pass held-out validation.
"""

from __future__ import annotations

import re

from stable_agent.skill_optimizer.edit_models import ALLOWED_OPERATIONS, BoundedEditResult, BoundedSkillEdit
from stable_agent.skill_optimizer.heldout_validator import HeldoutValidationResult
from stable_agent.skill_optimizer.rejected_buffer import RejectedBuffer
from stable_agent.skill_optimizer.textual_learning_rate import TextualLearningRate

HIGH_RISK_SECTION_RE = re.compile(r"(safety|human review|review gate|安全|人审|审核)", re.I)


class BoundedSkillEditor:
    def __init__(
        self,
        *,
        learning_rate: TextualLearningRate | None = None,
        rejected_buffer: RejectedBuffer | None = None,
    ) -> None:
        self.learning_rate = learning_rate or TextualLearningRate()
        self.rejected_buffer = rejected_buffer or RejectedBuffer()

    def apply(
        self,
        skill_markdown: str,
        edits: list[BoundedSkillEdit],
        validation: HeldoutValidationResult | None = None,
    ) -> BoundedEditResult:
        if not edits:
            return BoundedEditResult(True, skill_markdown, "没有编辑。")
        if len(edits) > self.learning_rate.max_sections_changed:
            return self._reject(edits[0], skill_markdown, "一次只能改一个 section。")

        edit = edits[0]
        if edit.operation not in ALLOWED_OPERATIONS:
            return self._reject(edit, skill_markdown, f"不支持的 edit operation: {edit.operation}")
        if self.rejected_buffer.is_repeat(edit):
            return self._reject(edit, skill_markdown, "该编辑与 rejected buffer 中的失败编辑重复。")
        if edit.operation.startswith("DELETE") and not self.learning_rate.allow_delete:
            return self._reject(edit, skill_markdown, "默认禁止删除。")
        if edit.operation.startswith("DELETE") and HIGH_RISK_SECTION_RE.search(edit.target):
            return self._reject(edit, skill_markdown, "禁止删除 safety / human review 相关规则。")
        if edit.operation in {"REPLACE_SECTION", "DELETE_SECTION"} and HIGH_RISK_SECTION_RE.search(edit.target):
            return self._reject(edit, skill_markdown, "高风险 section 不能被替换或删除。")
        if validation is not None and not validation.passed:
            return self._reject(edit, skill_markdown, validation.reason_zh)

        new_content = self._apply_one(skill_markdown, edit)
        changed_lines = _line_delta(skill_markdown, new_content)
        rules_added = 1 if edit.operation == "ADD_RULE" else 0
        ok, reason = self.learning_rate.validate(
            changed_lines=changed_lines,
            changed_sections=1,
            rules_added=rules_added,
            has_delete=edit.operation.startswith("DELETE"),
        )
        if not ok:
            return self._reject(edit, skill_markdown, reason)

        return BoundedEditResult(
            accepted=True,
            content=new_content,
            reason_zh="bounded edit accepted",
            changed_lines=changed_lines,
            changed_sections=1,
        )

    def _apply_one(self, markdown: str, edit: BoundedSkillEdit) -> str:
        if edit.operation == "ADD_SECTION":
            return markdown.rstrip() + f"\n\n## {edit.target}\n\n{edit.content.strip()}\n"
        if edit.operation == "ADD_RULE":
            return _append_rule(markdown, edit.target, edit.content)
        if edit.operation == "REPLACE_SECTION":
            return _replace_section(markdown, edit.target, edit.content)
        if edit.operation == "REPLACE_RULE":
            return _replace_rule(markdown, edit.target, edit.content)
        if edit.operation == "DELETE_SECTION":
            return _replace_section(markdown, edit.target, "")
        if edit.operation == "DELETE_RULE":
            return _replace_rule(markdown, edit.target, "")
        return markdown

    def _reject(self, edit: BoundedSkillEdit, original: str, reason: str) -> BoundedEditResult:
        self.rejected_buffer.add(edit, reason)
        return BoundedEditResult(
            accepted=False,
            content=original,
            reason_zh=reason,
            rejected=True,
            rejection_reason=reason,
        )


def _append_rule(markdown: str, section: str, rule: str) -> str:
    pattern = re.compile(rf"(^##+\s+{re.escape(section)}\s*$)", re.M)
    match = pattern.search(markdown)
    line = f"- {rule.strip()}"
    if not match:
        return markdown.rstrip() + f"\n\n## {section}\n\n{line}\n"
    insert_at = match.end()
    return markdown[:insert_at] + "\n" + line + markdown[insert_at:]


def _replace_section(markdown: str, section: str, content: str) -> str:
    pattern = re.compile(rf"^##+\s+{re.escape(section)}\s*$.*?(?=^##+\s+|\Z)", re.M | re.S)
    replacement = "" if not content.strip() else f"## {section}\n\n{content.strip()}\n\n"
    new, count = pattern.subn(replacement, markdown, count=1)
    if count == 0 and replacement:
        return markdown.rstrip() + "\n\n" + replacement
    return new


def _replace_rule(markdown: str, target: str, content: str) -> str:
    lines = markdown.splitlines()
    for idx, line in enumerate(lines):
        if target in line:
            if content.strip():
                lines[idx] = f"- {content.strip()}"
            else:
                lines.pop(idx)
            return "\n".join(lines) + "\n"
    return markdown.rstrip() + f"\n- {content.strip()}\n" if content.strip() else markdown


def _line_delta(a: str, b: str) -> int:
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    return abs(len(b_lines) - len(a_lines)) + sum(1 for x, y in zip(a_lines, b_lines) if x != y)
