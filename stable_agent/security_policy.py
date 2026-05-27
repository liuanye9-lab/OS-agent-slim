"""StableAgent OS 安全策略模块。

提供命令/路径风险分级功能，用于在执行前评估操作的安全风险。
支持四级风险分类：forbidden（禁止）、high（高风险）、medium（中风险）、low（低风险）。

约定：
- 所有方法返回 RiskLevel 枚举的字符串值
- 命令匹配忽略大小写，使用子串匹配
- 路径匹配使用前缀匹配
"""

from __future__ import annotations

from typing import Optional

from stable_agent.models import RiskLevel


class SecurityPolicy:
    """命令/路径风险分级。

    根据预定义的黑名单模式对命令和文件路径进行安全风险评估。
    用于决策是否需要人工审批以及在沙箱中执行前的安全检查。

    Attributes:
        FORBIDDEN_PATTERNS: 完全禁止的命令片段列表。
        HIGH_RISK_PATTERNS: 高风险命令片段列表。
        SENSITIVE_PATHS: 敏感路径前缀列表。
    """

    # 完全禁止的命令片段 —— 匹配到直接拒绝，不进入审批流程
    FORBIDDEN_PATTERNS: list[str] = [
        "rm -rf",
        "rm -r",
        "sudo rm",
        "dd if=",
        "mkfs.",
        ":(){ :|:& };:",  # fork bomb
        "> /dev/sda",
        "chmod 777 /",
        "curl | sh",
        "curl | bash",
        "| sh",  # 匹配任何通过管道传递给 sh 的模式
        "| bash",  # 匹配任何通过管道传递给 bash 的模式
        "wget -O - | sh",
        "git push --force origin main",
    ]

    # 高风险命令片段 —— 匹配到需要审批
    HIGH_RISK_PATTERNS: list[str] = [
        "rm ",
        "mv /",
        "cp /",
        "chmod ",
        "chown ",
        "kill ",
        "killall ",
        "shutdown",
        "reboot",
        "halt",
        "pip install",
        "npm install -g",
        "docker rm",
        "docker rmi",
        "git reset --hard",
        "git clean -fd",
    ]

    # 敏感路径前缀 —— 操作涉及这些路径视为中风险
    SENSITIVE_PATHS: list[str] = [
        "/etc/",
        "/System/",
        "/Library/",
        "~/.ssh",
        "~/.gnupg",
        "~/.aws",
        ".env",
        "credentials",
        "secrets",
        "/var/",
        "/usr/",
        "/bin/",
        "/sbin/",
        "~/Desktop",
        "~/Documents",
        "~/Downloads",
        "AppData",
        "Program Files",
    ]

    def classify_command(self, command: list[str]) -> str:
        """对命令进行风险分级。

        将命令列表拼接为字符串后，依次与 FORBIDDEN_PATTERNS
        和 HIGH_RISK_PATTERNS 进行子串匹配。匹配顺序为：
        禁止模式 → 高风险模式 → medium → low。

        Args:
            command: 命令 token 列表，如 ["rm", "-rf", "/tmp/cache"]。

        Returns:
            RiskLevel 枚举值：
            - "forbidden": 匹配到禁止模式，必须拒绝执行。
            - "high": 匹配到高风险模式，需要审批。
            - "medium": 未匹配到明确模式，保守评估。
            - "low": 明显安全的命令（如 echo、ls、pytest）。

        Examples:
            >>> sp = SecurityPolicy()
            >>> sp.classify_command(["rm", "-rf", "/"])
            'forbidden'
            >>> sp.classify_command(["ls", "-la"])
            'low'
        """
        if not command:
            return RiskLevel.LOW.value

        # 拼接命令为字符串用于子串匹配
        command_str = " ".join(command).lower()

        # 1. 先检查禁止模式
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern.lower() in command_str:
                return RiskLevel.FORBIDDEN.value

        # 2. 检查高风险模式
        for pattern in self.HIGH_RISK_PATTERNS:
            if pattern.lower() in command_str:
                return RiskLevel.HIGH.value

        # 3. 低风险命令白名单 —— 已知安全的命令
        low_risk_prefixes = (
            "echo", "ls", "cat", "head", "tail", "pwd", "whoami",
            "date", "env", "printenv", "which", "type", "cd",
            "pytest", "python -c", "python3 -c", "node -e",
            "git status", "git diff", "git log", "git branch",
            "grep", "find .", "wc", "sort", "uniq",
        )
        for prefix in low_risk_prefixes:
            if command_str.startswith(prefix):
                return RiskLevel.LOW.value

        # 4. 默认中风险
        return RiskLevel.MEDIUM.value

    def classify_path(self, path: str) -> str:
        """对文件路径进行风险分级。

        将路径与 SENSITIVE_PATHS 中的前缀进行匹配。匹配到敏感路径
        返回 medium，否则返回 low。

        Args:
            path: 文件系统路径字符串。

        Returns:
            RiskLevel 枚举值：
            - "medium": 路径匹配到敏感模式。
            - "low": 路径不涉及敏感区域。

        Examples:
            >>> sp = SecurityPolicy()
            >>> sp.classify_path("/etc/passwd")
            'medium'
            >>> sp.classify_path("/home/user/project/main.py")
            'low'
        """
        if not path:
            return RiskLevel.LOW.value

        # 统一使用小写进行匹配
        path_lower = path.lower()

        for sensitive in self.SENSITIVE_PATHS:
            # 支持前缀匹配或子串匹配（对于 .env, credentials 等无路径分隔符的模式）
            if path_lower.startswith(sensitive.lower()) or sensitive.lower() in path_lower:
                return RiskLevel.MEDIUM.value

        return RiskLevel.LOW.value

    def should_require_approval(
        self,
        action: str,
        risk: Optional[str] = None,
        command: Optional[list[str]] = None,
        path: Optional[str] = None,
    ) -> bool:
        """综合判断是否需要审批。

        决策规则：
        - forbidden → 直接拒绝（返回 True 表示需要审批，且审批不可通过）。
        - high → 必须审批。
        - medium + 敏感路径 → 需要审批。
        - low → 不需要审批。

        Args:
            action: 操作描述字符串。
            risk: 已知风险等级，None 表示需要自行判定。
            command: 命令列表，用于自动判定风险。
            path: 文件路径，用于辅助判定。

        Returns:
            True 表示需要进入审批流程，False 表示可直接执行。

        Examples:
            >>> sp = SecurityPolicy()
            >>> sp.should_require_approval("delete files", command=["rm", "-rf", "/"])
            True
            >>> sp.should_require_approval("list files", command=["ls", "-la"])
            False
        """
        # 如果未提供 risk，从 command 推断
        if risk is None:
            if command is not None:
                risk = self.classify_command(command)
            else:
                risk = RiskLevel.LOW.value

        # forbidden → 必须审批
        if risk == RiskLevel.FORBIDDEN.value:
            return True

        # high → 必须审批
        if risk == RiskLevel.HIGH.value:
            return True

        # medium + 敏感路径 → 需要审批
        if risk == RiskLevel.MEDIUM.value:
            if path is not None:
                path_risk = self.classify_path(path)
                if path_risk == RiskLevel.MEDIUM.value:
                    return True
            # medium 且无敏感路径，不需要审批
            return False

        # low → 不需要审批
        return False

    def get_risk_explanation(
        self,
        risk: str,
        command: Optional[list[str]] = None,
    ) -> str:
        """返回中文风险解释。

        根据风险等级和具体命令生成人类可读的风险说明文本。

        Args:
            risk: 风险等级字符串（RiskLevel 枚举值）。
            command: 命令列表，用于提供更具体的说明。

        Returns:
            中文风险解释文本。

        Examples:
            >>> sp = SecurityPolicy()
            >>> sp.get_risk_explanation("high", ["rm", "file.txt"])
            '高风险操作：该命令会删除文件且不可恢复，建议在沙箱中执行或进行人工确认。'
        """
        command_str = " ".join(command) if command else "未知命令"

        if risk == RiskLevel.FORBIDDEN.value:
            return (
                f"禁止操作：命令 '{command_str}' 包含高危操作模式，"
                f"可能造成不可逆的系统损害或安全漏洞，已被系统禁止执行。"
            )

        if risk == RiskLevel.HIGH.value:
            # 根据命令类型定制说明
            if command and any(kw in command_str.lower() for kw in ("rm ", "rm -", "rmdir")):
                return (
                    f"高风险操作：该命令会删除文件且不可恢复，"
                    f"建议在沙箱中执行或进行人工确认。"
                )
            if command and any(kw in command_str.lower() for kw in ("chmod", "chown")):
                return (
                    f"高风险操作：该命令会修改文件权限/所有者，"
                    f"可能影响系统安全性，请确认操作范围。"
                )
            if command and any(kw in command_str.lower() for kw in ("shutdown", "reboot", "halt")):
                return (
                    f"高风险操作：该命令会影响系统运行状态（关机/重启），"
                    f"请确认是否确实需要执行。"
                )
            if command and any(kw in command_str.lower() for kw in ("pip install", "npm install -g")):
                return (
                    f"高风险操作：该命令会在系统级别安装软件包，"
                    f"可能引入未知依赖或安全风险，请在沙箱环境中执行。"
                )
            if command and any(kw in command_str.lower() for kw in ("git reset --hard", "git clean -fd")):
                return (
                    f"高风险操作：该命令会不可逆地修改 Git 仓库状态，"
                    f"请确认已备份重要更改。"
                )
            return (
                f"高风险操作：命令 '{command_str}' 可能对系统或数据造成显著影响，"
                f"建议进行人工审批后执行。"
            )

        if risk == RiskLevel.MEDIUM.value:
            return (
                f"中风险操作：命令 '{command_str}' 存在一定风险，"
                f"请确认操作范围和影响后再执行。"
            )

        # low
        return (
            f"低风险操作：命令 '{command_str}' 属于常规操作，"
            f"风险可控，可直接执行。"
        )
