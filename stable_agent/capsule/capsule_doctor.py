"""stable_agent.capsule.capsule_doctor — 胶囊健康检查。

检查胶囊目录的完整性、安全性、格式正确性。
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from pathlib import Path

from stable_agent.capsule.manifest import ManifestManager
from stable_agent.capsule.capsule_manager import REQUIRED_DIRS
from stable_agent.capsule.schemas import CapsuleDoctorReport

logger = logging.getLogger(__name__)

# 敏感信息模式
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),       # OpenAI API key
    re.compile(r"AKIA[A-Z0-9]{16}"),           # AWS Access Key
    re.compile(r"OPENAI_API_KEY\s*=\s*\S+"),   # 环境变量
    re.compile(r"ANTHROPIC_API_KEY\s*=\s*\S+"),
    re.compile(r"password\s*[:=]\s*\S+", re.I),
]

# 大文件限制 (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# 过期日志保留天数
RAW_LOG_MAX_AGE_DAYS = 30


class CapsuleDoctor:
    """胶囊健康检查器。

    检查内容：
    - manifest 是否存在
    - schema_version 是否兼容
    - 必需目录是否存在
    - sqlite 文件是否可打开
    - jsonl 是否格式正确
    - 是否存在明显敏感信息泄漏
    - 是否存在超过限制的大文件
    - 是否存在过期 raw log 未清理
    """

    @staticmethod
    def check(capsule_path: str) -> CapsuleDoctorReport:
        """执行完整健康检查。

        Args:
            capsule_path: 胶囊根目录路径。

        Returns:
            CapsuleDoctorReport 实例。
        """
        report = CapsuleDoctorReport()
        capsule = Path(capsule_path)

        if not capsule.is_dir():
            report.ok = False
            report.health_score = 0.0
            report.errors.append(f"胶囊目录不存在: {capsule_path}")
            return report

        # 1. manifest 检查
        manifest_path = capsule / "capsule_manifest.json"
        if not manifest_path.exists():
            report.ok = False
            report.health_score *= 0.3
            report.errors.append("capsule_manifest.json 不存在")
        else:
            try:
                manifest = ManifestManager.load(manifest_path)
                if not ManifestManager.is_compatible(manifest):
                    report.ok = False
                    report.health_score *= 0.5
                    report.errors.append(
                        f"schema_version 不兼容: {manifest.schema_version}"
                    )
            except Exception as e:
                report.ok = False
                report.health_score *= 0.3
                report.errors.append(f"manifest 解析失败: {e}")

        # 2. 目录结构检查
        missing_dirs = [
            d for d in REQUIRED_DIRS
            if not (capsule / d).is_dir()
        ]
        if missing_dirs:
            report.warnings.append(f"缺失目录: {', '.join(missing_dirs)}")
            report.health_score *= max(0.5, 1.0 - len(missing_dirs) * 0.05)

        # 3. sqlite 文件检查
        for sqlite_file in capsule.rglob("*.sqlite"):
            try:
                conn = sqlite3.connect(str(sqlite_file))
                conn.execute("SELECT 1")
                conn.close()
            except Exception as e:
                report.warnings.append(f"sqlite 文件无法打开 {sqlite_file.name}: {e}")
                report.health_score *= 0.95

        # 4. jsonl 格式检查
        for jsonl_file in capsule.rglob("*.jsonl"):
            if jsonl_file.stat().st_size == 0:
                continue  # 空文件跳过
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        json.loads(line)
            except json.JSONDecodeError as e:
                report.warnings.append(
                    f"jsonl 格式错误 {jsonl_file.name} 第{i}行: {e}"
                )
                report.health_score *= 0.95

        # 5. 敏感信息检查
        for text_file in capsule.rglob("*"):
            if not text_file.is_file():
                continue
            if text_file.suffix.lower() not in {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}:
                continue
            try:
                content = text_file.read_text(encoding="utf-8", errors="ignore")
                for pattern in SENSITIVE_PATTERNS:
                    if pattern.search(content):
                        report.errors.append(
                            f"发现疑似敏感信息: {text_file.name}"
                        )
                        report.ok = False
                        report.health_score *= 0.7
                        break
            except Exception as e:
                logger.debug("sensitive check failed for %s: %s", text_file, e)

        # 6. 大文件检查
        for file_path in capsule.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                size = file_path.stat().st_size
                if size > MAX_FILE_SIZE_BYTES:
                    size_mb = size / (1024 * 1024)
                    report.warnings.append(
                        f"大文件 ({size_mb:.1f}MB): {file_path.name}"
                    )
                    report.suggestions.append(f"建议清理大文件: {file_path.name}")
            except OSError:
                pass

        # 7. 过期 raw log 检查
        raw_log = capsule / "memory" / "raw_episodes.jsonl"
        if raw_log.exists() and raw_log.stat().st_size > 0:
            import time
            now = time.time()
            expired_count = 0
            try:
                with open(raw_log, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            created = entry.get("created_at", 0)
                            if created and (now - created) > RAW_LOG_MAX_AGE_DAYS * 86400:
                                expired_count += 1
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.debug("raw log check failed: %s", e)
            if expired_count > 0:
                report.suggestions.append(
                    f"有 {expired_count} 条过期 raw episode 未清理"
                )

        # 计算统计信息
        report.stats = {
            "total_files": sum(1 for _ in capsule.rglob("*") if _.is_file()),
            "total_dirs": sum(1 for _ in capsule.rglob("*") if _.is_dir()),
            "missing_dirs": missing_dirs,
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "suggestion_count": len(report.suggestions),
        }

        # 确保 health_score 在合理范围
        report.health_score = max(0.0, min(1.0, round(report.health_score, 2)))

        return report
