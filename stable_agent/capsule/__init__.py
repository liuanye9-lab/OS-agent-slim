"""stable_agent.capsule — Agent Capsule 本地胶囊层。

提供用户长期 AI 使用资产的本地容器，支持创建、加载、验证、
导入导出胶囊。胶囊是面向 Vibe Coding 用户的可迁移 Agent Capsule，
通过 MCP 接入各 AI Coding 工具。
"""

from stable_agent.capsule.schemas import (
    CapsuleManifest,
    CapsuleDoctorReport,
    CapsuleStats,
)
from stable_agent.capsule.manifest import ManifestManager
from stable_agent.capsule.capsule_manager import CapsuleManager
from stable_agent.capsule.import_export import CapsuleImportExport
from stable_agent.capsule.capsule_doctor import CapsuleDoctor
from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager

__all__ = [
    "CapsuleManifest",
    "CapsuleDoctorReport",
    "CapsuleStats",
    "ManifestManager",
    "CapsuleManager",
    "CapsuleImportExport",
    "CapsuleDoctor",
    "MemoryLifecycleManager",
]
