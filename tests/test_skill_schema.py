"""tests/test_skill_schema.py — Skill Schema 测试。"""

from __future__ import annotations

import json
import time

import pytest

from stable_agent.skills.schema import (
    CurationOp,
    CurationOpType,
    RiskLevel,
    SkillMetadata,
    SkillPackage,
    SkillScope,
    SkillStatus,
    SkillTags,
    SkillVersion,
    generate_id,
)


class TestSkillMetadata:
    """SkillMetadata 测试。"""

    def test_create_default(self):
        """默认创建。"""
        m = SkillMetadata()
        assert m.skill_id == ""
        assert m.name == ""
        assert m.status == SkillStatus.ACTIVE
        assert m.scope == SkillScope.GLOBAL
        assert m.version == 1
        assert m.quality_score == 0.5

    def test_to_dict(self):
        """to_dict 序列化。"""
        m = SkillMetadata(
            skill_id="skill_test",
            name="test-skill",
            description="test description",
        )
        d = m.to_dict()
        assert d["skill_id"] == "skill_test"
        assert d["name"] == "test-skill"
        assert d["status"] == "active"
        assert d["scope"] == "global"

    def test_from_dict(self):
        """from_dict 反序列化。"""
        d = {
            "skill_id": "skill_test",
            "name": "test-skill",
            "description": "test",
            "status": "active",
            "scope": "global",
            "tags": {"topic": ["coding"]},
            "trigger_phrases": ["test"],
        }
        m = SkillMetadata.from_dict(d)
        assert m.skill_id == "skill_test"
        assert m.tags.topic == ["coding"]

    def test_json_roundtrip(self):
        """JSON 序列化/反序列化。"""
        m = SkillMetadata(
            skill_id="skill_test",
            name="test-skill",
            tags=SkillTags(topic=["coding"], capabilities=["test"]),
        )
        json_str = m.to_json()
        m2 = SkillMetadata.from_json(json_str)
        assert m2.skill_id == m.skill_id
        assert m2.tags.topic == m.tags.topic

    def test_status_enum(self):
        """状态枚举。"""
        for status in SkillStatus:
            m = SkillMetadata(status=status)
            assert m.status == status


class TestCurationOp:
    """CurationOp 测试。"""

    def test_source_run_required(self):
        """必须有 source_run。"""
        op = CurationOp(
            op_id="op_test",
            op=CurationOpType.INSERT_SKILL,
            source_run="run_test",
        )
        assert op.source_run == "run_test"

    def test_to_dict(self):
        """to_dict 序列化。"""
        op = CurationOp(
            op_id="op_test",
            op=CurationOpType.UPDATE_SKILL,
            skill_id="skill_test",
            source_run="run_test",
        )
        d = op.to_dict()
        assert d["op"] == "update_skill"
        assert d["source_run"] == "run_test"

    def test_json_roundtrip(self):
        """JSON 序列化/反序列化。"""
        op = CurationOp(
            op_id="op_test",
            op=CurationOpType.INSERT_SKILL,
            new_skill=SkillMetadata(skill_id="skill_test"),
            source_run="run_test",
        )
        json_str = op.to_json()
        op2 = CurationOp.from_json(json_str)
        assert op2.op == CurationOpType.INSERT_SKILL
        assert op2.new_skill is not None


class TestSkillVersion:
    """SkillVersion 测试。"""

    def test_fields(self):
        """字段正确。"""
        v = SkillVersion(
            id="ver_test",
            skill_id="skill_test",
            version=1,
            parent_version=None,
            op_id="op_test",
            content_hash="abc123",
        )
        assert v.skill_id == "skill_test"
        assert v.version == 1
        assert v.parent_version is None

    def test_to_dict(self):
        """to_dict 序列化。"""
        v = SkillVersion(
            id="ver_test",
            skill_id="skill_test",
            version=1,
        )
        d = v.to_dict()
        assert d["id"] == "ver_test"
        assert d["version"] == 1


class TestSkillTags:
    """SkillTags 测试。"""

    def test_default(self):
        """默认值。"""
        t = SkillTags()
        assert t.topic == []
        assert t.capabilities == []

    def test_from_dict_string(self):
        """从 JSON 字符串创建。"""
        t = SkillTags.from_dict('{"topic": ["test"]}')
        assert t.topic == ["test"]

    def test_from_dict(self):
        """从字典创建。"""
        t = SkillTags.from_dict({"topic": ["test"], "capabilities": ["cap1"]})
        assert t.topic == ["test"]
        assert t.capabilities == ["cap1"]


class TestGenerateId:
    """generate_id 测试。"""

    def test_with_prefix(self):
        """带前缀。"""
        id1 = generate_id("skill_")
        assert id1.startswith("skill_")
        assert len(id1) > 6

    def test_without_prefix(self):
        """不带前缀。"""
        id1 = generate_id()
        assert len(id1) > 0

    def test_unique(self):
        """唯一性。"""
        ids = {generate_id("test_") for _ in range(100)}
        assert len(ids) == 100
