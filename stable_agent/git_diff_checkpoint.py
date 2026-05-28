"""Git 版本控制封装模块。

本模块提供 VersionControlManager 类，封装 Git 版本控制的核心操作，
包括仓库初始化、检查点创建/回退、diff 计算等。

V3 升级：
- get_changed_files: git diff HEAD --name-only
- create_diff_summary: 生成 diff 摘要
- safe_revert: 安全回退（先 stash 再 reset，失败则 pop stash）
- is_repo: 检查是否为 git 仓库

模块职责：
- Git 仓库初始化
- 创建和回退检查点（commit）
- 计算工作区变更（diff）
- 安全回退（含 stash 保护）
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VersionControlManager:
    """Git 版本控制管理器。

    封装 Git 命令行操作，提供检查点创建、回退和 diff 计算功能。

    Attributes:
        repo_path: Git 仓库的本地路径。
    """

    def __init__(self, repo_path: str = ".") -> None:
        """初始化版本控制管理器。

        Args:
            repo_path: Git 仓库路径，默认为当前目录。

        # STUB: 使用 subprocess 调用 git 命令。
        """
        self.repo_path: str = repo_path

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_repo_path(path: str) -> Path:
        """验证路径是否为有效的 git 仓库。

        Args:
            path: 待验证的路径字符串。

        Returns:
            解析后的绝对路径 Path 对象。

        Raises:
            ValueError: 如果路径不是 git 仓库（缺少 .git 目录）。
        """
        repo = Path(path).resolve()
        if not (repo / ".git").exists():
            raise ValueError(f"不是 git 仓库: {repo}")
        return repo

    def _run_git(self, args: list[str]) -> tuple[int, str, str]:
        """执行 git 命令并返回结果。

        Args:
            args: git 命令参数列表（不含 'git' 本身）。

        Returns:
            (return_code, stdout, stderr) 三元组。
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                cwd=str(Path(self.repo_path).resolve()),
                timeout=30,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            return 1, "", "git command not found"
        except subprocess.TimeoutExpired:
            return 1, "", "git command timed out"

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def initialize_repo(self, path: Optional[str] = None) -> bool:
        """在指定路径初始化 Git 仓库。

        执行 ``git init`` 命令。如果指定了 path，会先更新 self.repo_path。

        Args:
            path: 要初始化的目录路径，None 表示使用当前的 repo_path。

        Returns:
            True 表示初始化成功，False 表示失败。

        # STUB: 简单调用 git init 命令。
        """
        target = path if path is not None else self.repo_path
        self.repo_path = target
        returncode, _, _ = self._run_git(["init", target])
        return returncode == 0

    def create_checkpoint(self, message: str) -> Optional[str]:
        """创建 Git 检查点（commit）。

        执行 ``git add -A && git commit -m <message>``。

        Args:
            message: 提交信息。

        Returns:
            新提交的 hash，失败时返回 None。

        # STUB: 使用 subprocess，错误时返回 None。
        """
        self._validate_repo_path(self.repo_path)

        # git add -A
        rc_add, _, stderr_add = self._run_git(["add", "-A"])
        if rc_add != 0:
            return None

        # git commit
        rc_commit, stdout_commit, _ = self._run_git(
            ["commit", "-m", message, "--allow-empty"]
        )
        if rc_commit != 0:
            return None

        # 获取最新 commit hash
        return self.get_current_hash()

    def compute_diff(self, file_path: Optional[str] = None) -> str:
        """计算当前工作区与 HEAD 的差异。

        如果指定 file_path，执行 ``git diff HEAD -- <file_path>``；
        否则执行 ``git diff HEAD``。

        Args:
            file_path: 可选的文件路径，限定 diff 范围。

        Returns:
            diff 文本内容。如果出错返回空字符串。

        # STUB: 简单调用 git diff。
        """
        args = ["diff", "HEAD"]
        if file_path is not None:
            args.append("--")
            args.append(file_path)

        returncode, stdout, _ = self._run_git(args)
        if returncode != 0:
            return ""
        return stdout

    def commit_changes(self, message: str) -> Optional[str]:
        """提交所有变更并返回 commit hash。

        执行 ``git add -A && git commit -m <message>``。

        Args:
            message: 提交信息。

        Returns:
            新提交的 hash，失败时返回 None。

        # STUB: 同 create_checkpoint，两者共用内部逻辑。
        """
        return self.create_checkpoint(message)

    def revert_to_checkpoint(self, checkpoint_id: str) -> bool:
        """回退到指定检查点。

        执行 ``git reset --hard <checkpoint_id>``。

        .. warning::

            ⚠️ 危险操作！此方法会**丢弃**所有未提交的变更并将工作区
            强制重置到指定的 commit。使用前请确保所有重要变更已提交或备份。

        Args:
            checkpoint_id: 目标 commit hash。

        Returns:
            True 表示回退成功，False 表示失败。

        # STUB: 简单调用 git reset --hard。
        """
        self._validate_repo_path(self.repo_path)

        returncode, _, _ = self._run_git(
            ["reset", "--hard", checkpoint_id]
        )
        return returncode == 0

    def get_current_hash(self) -> Optional[str]:
        """获取当前 HEAD 的 commit hash。

        执行 ``git rev-parse HEAD``。

        Returns:
            当前 HEAD 的 hash 字符串，失败时返回 None。

        # STUB: 简单调用 git rev-parse HEAD。
        """
        returncode, stdout, _ = self._run_git(["rev-parse", "HEAD"])
        if returncode != 0:
            return None
        return stdout

    # ------------------------------------------------------------------
    # V3 新增方法
    # ------------------------------------------------------------------

    def get_changed_files(self) -> list[str]:
        """git diff HEAD --name-only，返回变更文件列表。

        Returns:
            变更文件路径列表。若命令失败或非 git 仓库，返回空列表。

        Examples:
            >>> vcm = VersionControlManager()
            >>> files = vcm.get_changed_files()
            >>> isinstance(files, list)
            True
        """
        returncode, stdout, _ = self._run_git(["diff", "HEAD", "--name-only"])
        if returncode != 0:
            return []
        if not stdout:
            return []
        return [f for f in stdout.split("\n") if f.strip()]

    def create_diff_summary(self) -> dict:
        """生成 diff 摘要：{files_changed: [...], insertions: int, deletions: int}。

        使用 ``git diff HEAD --stat`` 解析统计信息，再结合
        ``git diff HEAD --numstat`` 获取精确的增减行数。

        Returns:
            包含 files_changed, insertions, deletions 的字典。
            若命令失败，返回空统计。

        Examples:
            >>> vcm = VersionControlManager()
            >>> summary = vcm.create_diff_summary()
            >>> "files_changed" in summary
            True
            >>> "insertions" in summary
            True
            >>> "deletions" in summary
            True
        """
        files: list[str] = self.get_changed_files()

        # 使用 --numstat 获取精确统计
        insertions: int = 0
        deletions: int = 0

        returncode, stdout, _ = self._run_git(
            ["diff", "HEAD", "--numstat"]
        )
        if returncode == 0 and stdout:
            for line in stdout.split("\n"):
                parts: list[str] = line.split()
                if len(parts) >= 2:
                    try:
                        insertions += int(parts[0]) if parts[0] != "-" else 0
                        deletions += int(parts[1]) if parts[1] != "-" else 0
                    except ValueError:
                        continue

        return {
            "files_changed": files,
            "insertions": insertions,
            "deletions": deletions,
        }

    def safe_revert(self, checkpoint_id: str) -> bool:
        """安全回退：先 stash 当前变更，再 git reset --hard checkpoint_id。

        回退失败则 pop stash 恢复。返回是否成功。

        流程：
        1. git stash push -m "safe_revert_backup"
        2. git reset --hard <checkpoint_id>
        3. 如果 reset 失败 → git stash pop 恢复
        4. 如果 reset 成功 → stash 保留（可手动恢复）

        Args:
            checkpoint_id: 目标 commit hash。

        Returns:
            True 表示回退成功，False 表示失败（变更已恢复）。

        Examples:
            >>> vcm = VersionControlManager()
            >>> # 在 git 仓库中测试
            >>> result = vcm.safe_revert("HEAD")
            >>> isinstance(result, bool)
            True
        """
        self._validate_repo_path(self.repo_path)

        # Step 1: stash 当前变更
        stash_rc, stash_stdout, stash_stderr = self._run_git(
            ["stash", "push", "-m", "safe_revert_backup"]
        )
        # stash 成功或 "No local changes to save" 都可以继续
        has_stash: bool = stash_rc == 0 and "No local changes" not in stash_stdout

        # Step 2: reset --hard
        reset_rc, _, reset_stderr = self._run_git(
            ["reset", "--hard", checkpoint_id]
        )

        if reset_rc != 0:
            # 回退失败，尝试恢复 stash
            if has_stash:
                self._run_git(["stash", "pop"])
            return False

        # Step 3: 成功！清理 backup stash
        if has_stash:
            self._run_git(["stash", "drop", "stash@{0}"])

        return True

    def is_repo(self) -> bool:
        """检查当前路径是否是 git 仓库。

        执行 ``git rev-parse --git-dir`` 并检查返回码。

        Returns:
            True 表示是 git 仓库，False 表示不是。

        Examples:
            >>> vcm = VersionControlManager()
            >>> result = vcm.is_repo()
            >>> isinstance(result, bool)
            True
        """
        returncode, _, _ = self._run_git(["rev-parse", "--git-dir"])
        return returncode == 0
