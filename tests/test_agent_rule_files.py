"""Tests for AGENTS.md and CLAUDE.md calling rule compliance.

Verifies that both agent rule files contain:
- Standard JSON call example with `task_input` and `open_dashboard` fields
- Return field清单 (result, risk_assessment, requires_human_review, task_id)
- Effectiveness record_example with all required fields
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# --- helpers ---

def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _has_json_block(text: str) -> bool:
    """Check if file contains a ```json code block."""
    return "```json" in text


def _has_task_input_in_json(text: str) -> bool:
    """Check if any JSON block contains `task_input` field."""
    # Match task_input inside json code blocks
    pattern = r'```json[^`]*"task_input"\s*:'
    return bool(re.search(pattern, text, re.DOTALL))


def _has_open_dashboard_in_json(text: str) -> bool:
    """Check if any JSON block contains `open_dashboard` field."""
    pattern = r'```json[^`]*"open_dashboard"\s*:'
    return bool(re.search(pattern, text, re.DOTALL))


def _has_old_task_field_in_json(text: str) -> bool:
    """Check if any JSON block still uses the old `task` field (not task_input)."""
    # Match "task": inside json blocks, but NOT "task_input"
    pattern = r'```json[^`]*"(?<!task_)task"\s*:'
    return bool(re.search(pattern, text, re.DOTALL))


def _has_return_fields(text: str) -> bool:
    """Check if file lists all required return fields."""
    required = ["result", "risk_assessment", "requires_human_review", "task_id"]
    return all(field in text for field in required)


def _has_effectiveness_record(text: str) -> bool:
    """Check if file contains effectiveness record example with required fields."""
    required = [
        "record_effectiveness",
        "task_id",
        "mode",
        "success",
        "edits_made",
        "tokens_used",
        "intent_drift",
    ]
    return all(field in text for field in required)


# --- AGENTS.md tests ---

class TestAgentsMD:
    """Verify AGENTS.md calling rules."""

    def setup_method(self):
        self.text = _read("AGENTS.md")

    def test_file_exists(self):
        assert (ROOT / "AGENTS.md").exists()

    def test_has_json_block(self):
        assert _has_json_block(self.text), "AGENTS.md should contain ```json blocks"

    def test_has_task_input_in_json(self):
        assert _has_task_input_in_json(self.text), (
            "AGENTS.md JSON example must use `task_input` field"
        )

    def test_has_open_dashboard_in_json(self):
        assert _has_open_dashboard_in_json(self.text), (
            "AGENTS.md JSON example must include `open_dashboard` field"
        )

    def test_no_old_task_field(self):
        assert not _has_old_task_field_in_json(self.text), (
            "AGENTS.md should not use old `task` field in JSON examples; use `task_input`"
        )

    def test_has_return_field_list(self):
        assert _has_return_fields(self.text), (
            "AGENTS.md must list return fields: result, risk_assessment, "
            "requires_human_review, task_id"
        )

    def test_has_effectiveness_record_example(self):
        assert _has_effectiveness_record(self.text), (
            "AGENTS.md must contain effectiveness record example with all required fields"
        )

    def test_record_example_in_json_block(self):
        """Effectiveness record example must also be in a JSON block."""
        pattern = r'```json[^`]*record_effectiveness[^`]*'
        assert re.search(pattern, self.text, re.DOTALL), (
            "Effectiveness record example must be inside ```json block"
        )


# --- CLAUDE.md tests ---

class TestClaudeMD:
    """Verify CLAUDE.md calling rules."""

    def setup_method(self):
        self.text = _read("CLAUDE.md")

    def test_file_exists(self):
        assert (ROOT / "CLAUDE.md").exists()

    def test_has_json_block(self):
        assert _has_json_block(self.text), "CLAUDE.md should contain ```json blocks"

    def test_has_task_input_in_json(self):
        assert _has_task_input_in_json(self.text), (
            "CLAUDE.md JSON example must use `task_input` field"
        )

    def test_has_open_dashboard_in_json(self):
        assert _has_open_dashboard_in_json(self.text), (
            "CLAUDE.md JSON example must include `open_dashboard` field"
        )

    def test_no_old_task_field_in_call_example(self):
        """CLAUDE.md call example should not use old `task` field."""
        # The call example section uses task_input, effectiveness section uses task_id
        # We only check the call example (before the return fields section)
        call_section = self.text.split("返回字段清单")[0]
        pattern = r'```json[^`]*"(?<!task_)task"\s*:'
        assert not re.search(pattern, call_section, re.DOTALL), (
            "CLAUDE.md call example should use `task_input` not `task`"
        )

    def test_has_return_field_list(self):
        assert _has_return_fields(self.text), (
            "CLAUDE.md must list return fields: result, risk_assessment, "
            "requires_human_review, task_id"
        )

    def test_has_effectiveness_record_example(self):
        assert _has_effectiveness_record(self.text), (
            "CLAUDE.md must contain effectiveness record example with all required fields"
        )

    def test_record_example_in_json_block(self):
        """Effectiveness record example must be in a JSON block."""
        pattern = r'```json[^`]*record_effectiveness[^`]*'
        assert re.search(pattern, self.text, re.DOTALL), (
            "Effectiveness record example must be inside ```json block"
        )
