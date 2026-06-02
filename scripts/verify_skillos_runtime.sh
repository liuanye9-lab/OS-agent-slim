#!/bin/bash
# verify_skillos_runtime.sh — SkillOS Runtime 验证脚本
#
# 用法:
#   bash scripts/verify_skillos_runtime.sh

set -e

echo "========================================="
echo "StableAgent OS V12 SkillOS Runtime 验证"
echo "========================================="
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    echo -n "  [$desc] "
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC}"
        FAIL=$((FAIL + 1))
    fi
}

echo "1. 检查模块导入"
check "skills.schema" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.schema import SkillMetadata'"
check "skills.repo" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.repo import SkillRepo'"
check "skills.retriever" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.retriever import SkillRetriever'"
check "skills.curator" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.curator_service import SkillCuratorService'"
check "skills.judges" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.judges import OutcomeJudge, ContentJudge'"
check "skills.rollback" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.rollback import SkillRollbackManager'"
check "skills.attribution" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.attribution import SkillAttribution'"
check "skills.replay" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.replay import GroupedReplayLite'"
check "skills.lint" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.skill_lint import SkillLinter'"
check "skills.package" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.package_manager import SkillPackageManager'"

echo ""
echo "2. 检查 SkillRepo 初始化"
check "repo.init" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.repo import SkillRepo; r = SkillRepo(); assert r.db_path.exists()'"

echo ""
echo "3. 检查默认种子技能"
check "seed skills" "PYTHONPATH=. .venv/bin/python -c 'from stable_agent.skills.repo import SkillRepo; r = SkillRepo(); s = r.list_skills(); assert len(s) >= 7'"

echo ""
echo "4. 检查 CLI 命令"
check "skill health" "PYTHONPATH=. .venv/bin/python -m stable_agent.cli skill health --json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d[\"ok\"]'"
check "skill list" "PYTHONPATH=. .venv/bin/python -m stable_agent.cli skill list --json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d[\"ok\"]'"
check "skill search" "PYTHONPATH=. .venv/bin/python -m stable_agent.cli skill search --query test --json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d[\"ok\"]'"

echo ""
echo "5. 检查测试"
check "test_skill_schema" "PYTHONPATH=. .venv/bin/python -m pytest tests/test_skill_schema.py -q --tb=no 2>/dev/null | grep -q 'passed'"
check "test_skill_repo" "PYTHONPATH=. .venv/bin/python -m pytest tests/test_skill_repo.py -q --tb=no 2>/dev/null | grep -q 'passed'"
check "test_skill_retriever" "PYTHONPATH=. .venv/bin/python -m pytest tests/test_skill_retriever.py -q --tb=no 2>/dev/null | grep -q 'passed'"

echo ""
echo "========================================="
echo "结果: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "========================================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi
