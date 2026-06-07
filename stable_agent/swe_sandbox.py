"""安全沙箱执行环境模块。

本模块提供 Sandbox 类，用于在隔离环境中执行命令和脚本。
对 subprocess.run 进行封装，提供超时控制、异常捕获和临时脚本执行功能。

V3 升级：
- 集成 SecurityPolicy：run_safe_command 方法
- __init__ 新增 security_policy 参数

模块职责：
- 安全地执行 shell 命令
- 执行 Python 脚本（通过临时文件）
- 安全地运行任意函数
- 超时和异常保护
- 安全策略检查的命令执行

.. warning::
    生产环境应用容器隔离，限制文件系统和网络访问。
    不要在生产环境执行不可信代码。
"""

from __future__ import annotations

import subprocess
import tempfile
import os
import sys
from typing import Any, Callable, Optional, TYPE_CHECKING

from stable_agent.models import SandboxResult

if TYPE_CHECKING:
    from stable_agent.security_policy import SecurityPolicy


class Sandbox:
    """安全沙箱执行环境。

    封装 subprocess 调用，提供超时控制、临时脚本执行和
    函数安全调用功能。

    Attributes:
        timeout: 命令默认超时秒数。
        allow_network: 是否允许网络访问（STUB: 当前仅标记）。
        security_policy: 可选的安全策略实例。
    """

    def __init__(
        self,
        timeout: int = 30,
        allow_network: bool = False,
        security_policy: Optional["SecurityPolicy"] = None,
    ) -> None:
        """初始化沙箱环境。

        Args:
            timeout: 命令默认超时秒数，默认 30。
            allow_network: 是否允许网络访问。
                # STUB: 当前仅标记，未来通过容器网络策略实现。
            security_policy: 可选的安全策略实例，用于 run_safe_command。

        Raises:
            ValueError: 如果 timeout <= 0。
        """
        if timeout <= 0:
            raise ValueError(f"timeout must be a positive integer, got {timeout}")
        self.timeout: int = timeout
        self.allow_network: bool = allow_network
        self.security_policy: Optional["SecurityPolicy"] = security_policy

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def run_command(
        self,
        command: list[str],
        timeout: int | None = None,
        cwd: str | None = None,
    ) -> SandboxResult:
        """在沙箱中执行命令。

        使用 subprocess.run 执行命令，捕获 stdout/stderr。
        超时或异常时返回适当的 SandboxResult。

        .. note::
            生产环境应用容器隔离，限制文件系统和网络访问。

        Args:
            command: 命令及其参数列表，如 ["echo", "hello"]。
            timeout: 超时秒数，None 使用默认值。
            cwd: 工作目录，None 使用当前目录。

        Returns:
            SandboxResult 包含 return_code、stdout 和 stderr。

        Examples:
            >>> sandbox = Sandbox(timeout=5)
            >>> result = sandbox.run_command(["echo", "hello"])
            >>> result.return_code
            0
            >>> "hello" in result.stdout
            True
        """
        effective_timeout: int = timeout if timeout is not None else self.timeout
        normalized_command = list(command)
        if normalized_command and normalized_command[0] == "python":
            normalized_command[0] = sys.executable

        try:
            proc: subprocess.CompletedProcess[str] = subprocess.run(
                normalized_command,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=cwd,
            )
            return SandboxResult(
                return_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                return_code=-1,
                stdout="",
                stderr=f"Command timed out after {effective_timeout}s",
            )
        except FileNotFoundError:
            return SandboxResult(
                return_code=-2,
                stdout="",
                stderr=f"Command not found: {command[0] if command else ''}",
            )
        except Exception as exc:
            return SandboxResult(
                return_code=-3,
                stdout="",
                stderr=f"Sandbox execution error: {exc}",
            )

    def run_safe_command(
        self,
        command: list[str],
        timeout: int | None = None,
        cwd: str | None = None,
    ) -> SandboxResult:
        """先通过 security_policy 检查命令风险等级，再决定是否执行。

        检查规则：
        - forbidden → 返回 SandboxResult(-1, "", "FORBIDDEN: 该命令被安全策略禁止")
        - high/medium → 返回 SandboxResult(-1, "", "APPROVAL_REQUIRED: 需要审批")
        - low → 正常执行（委托给 run_command）

        如果未注入 security_policy，所有命令作为低风险直接执行。

        Args:
            command: 命令及其参数列表。
            timeout: 超时秒数，None 使用默认值。
            cwd: 工作目录，None 使用当前目录。

        Returns:
            SandboxResult 包含执行结果或拒绝原因。

        Examples:
            >>> sandbox = Sandbox(timeout=5)
            >>> result = sandbox.run_safe_command(["echo", "hello"])
            >>> result.return_code
            0
            >>> from stable_agent.security_policy import SecurityPolicy
            >>> sandbox2 = Sandbox(timeout=5, security_policy=SecurityPolicy())
            >>> result2 = sandbox2.run_safe_command(["rm", "-rf", "/"])
            >>> result2.return_code
            -1
            >>> "FORBIDDEN" in result2.stderr
            True
        """
        # 无安全策略 → 直接执行
        if self.security_policy is None:
            return self.run_command(command, timeout=timeout, cwd=cwd)

        # 有安全策略 → 检查风险等级
        risk: str = self.security_policy.classify_command(command)

        if risk == "forbidden":
            return SandboxResult(
                return_code=-1,
                stdout="",
                stderr="FORBIDDEN: 该命令被安全策略禁止",
            )

        if risk in ("high", "medium"):
            return SandboxResult(
                return_code=-1,
                stdout="",
                stderr="APPROVAL_REQUIRED: 需要审批",
            )

        # low 风险 → 正常执行
        return self.run_command(command, timeout=timeout, cwd=cwd)

    def execute_script(
        self,
        script: str,
        timeout: int | None = None,
    ) -> SandboxResult:
        """在沙箱中执行 Python 脚本。

        将脚本写入临时 .py 文件，用当前 Python 解释器执行，
        执行后自动清理临时文件。

        .. warning::
            不要在生产环境执行不可信代码。此方法设计用于
            受控环境中的自动化测试和工具调用。

        Args:
            script: 要执行的 Python 脚本源代码。
            timeout: 超时秒数，None 使用默认值。

        Returns:
            SandboxResult 包含执行结果。

        Examples:
            >>> sandbox = Sandbox(timeout=5)
            >>> result = sandbox.execute_script("print('hello sandbox')")
            >>> result.return_code
            0
            >>> "hello sandbox" in result.stdout
            True
        """
        effective_timeout: int = timeout if timeout is not None else self.timeout

        tmp_file = None
        try:
            # 创建临时文件，suffix=".py" 确保 Python 解释器可以识别
            tmp_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            )
            tmp_file.write(script)
            tmp_file.flush()
            tmp_file.close()

            # 使用当前 Python 解释器执行
            result: SandboxResult = self.run_command(
                command=[sys.executable, tmp_file.name],
                timeout=effective_timeout,
            )
            return result
        except Exception as exc:
            return SandboxResult(
                return_code=-3,
                stdout="",
                stderr=f"Script execution error: {exc}",
            )
        finally:
            # 清理临时文件
            if tmp_file is not None:
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass  # 文件已被系统清理，忽略

    def safe_run(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """安全地运行任意函数，捕获所有异常。

        在 try/except 中运行 func(*args, **kwargs)。
        成功返回函数结果，失败返回异常字符串。

        Args:
            func: 要执行的函数。
            *args: 传递给函数的位置参数。
            **kwargs: 传递给函数的关键字参数。

        Returns:
            函数返回值，或异常描述字符串。

        Examples:
            >>> sandbox = Sandbox()
            >>> sandbox.safe_run(lambda x, y: x + y, 1, 2)
            3
            >>> isinstance(sandbox.safe_run(lambda: 1/0), str)
            True
        """
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            return f"Safe run error: {exc}"

    def set_timeout(self, timeout: int) -> None:
        """设置默认超时时间。

        Args:
            timeout: 新的默认超时秒数。

        Raises:
            ValueError: 如果 timeout <= 0。
        """
        if timeout <= 0:
            raise ValueError(f"timeout must be a positive integer, got {timeout}")
        self.timeout = timeout
