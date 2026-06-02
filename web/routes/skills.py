"""web.routes.skills — SkillOS Dashboard API 路由。

提供技能库管理、策展操作、版本回滚等 API。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 延迟导入
_repo = None
_retriever = None
_curator = None
_rollback_manager = None
_attribution = None


def _get_repo():
    global _repo
    if _repo is None:
        from stable_agent.skills.repo import SkillRepo
        _repo = SkillRepo()
    return _repo


def _get_retriever():
    global _retriever
    if _retriever is None:
        from stable_agent.skills.retriever import SkillRetriever
        _retriever = SkillRetriever(_get_repo())
    return _retriever


def _get_curator():
    global _curator
    if _curator is None:
        from stable_agent.skills.curator_service import SkillCuratorService
        _curator = SkillCuratorService(_get_repo())
    return _curator


def _get_rollback_manager():
    global _rollback_manager
    if _rollback_manager is None:
        from stable_agent.skills.rollback import SkillRollbackManager
        _rollback_manager = SkillRollbackManager(_get_repo())
    return _rollback_manager


def _get_attribution():
    global _attribution
    if _attribution is None:
        from stable_agent.skills.attribution import SkillAttribution
        _attribution = SkillAttribution(_get_repo())
    return _attribution


def register_skill_routes(app) -> None:
    """注册技能相关路由。"""
    app.include_router(router)


# ===================================================================
# API 端点
# ===================================================================


@router.get("/api/skills")
async def list_skills(
    status: str = "active",
    scope: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """列出技能。"""
    try:
        repo = _get_repo()
        skills = repo.list_skills(status=status, scope=scope, limit=limit, offset=offset)
        return {
            "ok": True,
            "skills": [s.to_dict() for s in skills],
            "count": len(skills),
        }
    except Exception as exc:
        logger.error("list_skills failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/skills/health")
async def skill_health():
    """技能库健康检查。"""
    try:
        repo = _get_repo()
        return repo.health_check()
    except Exception as exc:
        logger.error("skill_health failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能详情。"""
    try:
        repo = _get_repo()
        skill = repo.get_skill(skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

        # 获取版本历史
        versions = repo.get_versions(skill_id)

        # 获取 curation events
        events = repo.get_curation_events(skill_id=skill_id, limit=20)

        return {
            "ok": True,
            "skill": skill.to_dict(),
            "versions": [v.to_dict() for v in versions],
            "curation_events": events,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_skill failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/skills/{skill_id}/diff")
async def get_skill_diff(skill_id: str, version_a: int = 1, version_b: int = 2):
    """获取技能版本差异。"""
    try:
        manager = _get_rollback_manager()
        diff = manager.compare_versions(skill_id, version_a, version_b)
        return diff
    except Exception as exc:
        logger.error("get_skill_diff failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/api/skills/search")
async def search_skills(request: Request):
    """搜索技能。"""
    try:
        body = await request.json()
        query = body.get("query", "")
        top_k = body.get("top_k", 5)

        retriever = _get_retriever()
        results = retriever.search(query, top_k=top_k)

        return {
            "ok": True,
            "results": [r.to_dict() for r in results],
            "count": len(results),
        }
    except Exception as exc:
        logger.error("search_skills failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.post("/api/skills/rollback")
async def rollback_skill(request: Request):
    """回滚技能版本。"""
    try:
        body = await request.json()
        skill_id = body.get("skill_id", "")
        target_version = body.get("target_version", 1)

        manager = _get_rollback_manager()
        result = manager.rollback(
            skill_id=skill_id,
            target_version=target_version,
            reason="dashboard rollback",
        )

        if result is None:
            return {"ok": False, "error": f"Rollback failed: version {target_version} not found"}

        return {
            "ok": True,
            "skill_id": skill_id,
            "new_version": result.version,
            "rolled_back_to": target_version,
        }
    except Exception as exc:
        logger.error("rollback_skill failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/skills/attribution/summary")
async def attribution_summary():
    """技能归因摘要。"""
    try:
        attr = _get_attribution()
        return attr.compute_repo_summary().to_dict()
    except Exception as exc:
        logger.error("attribution_summary failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/skills/attribution/{skill_id}")
async def skill_attribution(skill_id: str):
    """技能归因详情。"""
    try:
        attr = _get_attribution()
        return attr.compute_skill_summary(skill_id).to_dict()
    except Exception as exc:
        logger.error("skill_attribution failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/api/skills/curation/events")
async def curation_events(skill_id: str | None = None, limit: int = 50):
    """获取 curation 事件。"""
    try:
        repo = _get_repo()
        events = repo.get_curation_events(skill_id=skill_id, limit=limit)
        return {
            "ok": True,
            "events": events,
            "count": len(events),
        }
    except Exception as exc:
        logger.error("curation_events failed: %s", exc)
        return {"ok": False, "error": str(exc)}
