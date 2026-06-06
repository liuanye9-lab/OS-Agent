"""Textual learning-rate constraints for SkillOpt-style edits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextualLearningRate:
    max_lines_changed: int = 12
    max_sections_changed: int = 1
    max_rules_added: int = 2
    allow_delete: bool = False

    def validate(
        self,
        *,
        changed_lines: int,
        changed_sections: int,
        rules_added: int = 0,
        has_delete: bool = False,
    ) -> tuple[bool, str]:
        if changed_lines > self.max_lines_changed:
            return False, "changed_lines exceeds textual learning rate"
        if changed_sections > self.max_sections_changed:
            return False, "changed_sections exceeds textual learning rate"
        if rules_added > self.max_rules_added:
            return False, "rules_added exceeds textual learning rate"
        if has_delete and not self.allow_delete:
            return False, "delete operations are disabled"
        return True, "ok"
