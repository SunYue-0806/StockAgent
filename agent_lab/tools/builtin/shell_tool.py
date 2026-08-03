import os
from typing import Any, Dict

from agent_lab.tools.tool_manager import tool


@tool
def execute_bash(
        command: str,
        workdir: str = "",
        timeout: int = 300,
        run_in_background: bool = False,
        shell_type: str = "auto",
        operation: Any = None,
) -> Dict[str, Any]:
    """在系统 Shell 中执行 Bash 命令，支持后台运行与超时控制。

    Args:
        command: 要执行的 Bash 命令字符串
        workdir: (可选) 命令执行的目标工作目录。留空则使用当前工作目录
        timeout: (可选) 命令执行超时时间（秒），默认 300 秒
        run_in_background: (可选) 是否在后台异步运行命令，默认为 False
        shell_type: (可选) 指定 Shell 类型 ("bash", "sh", "zsh", "auto")，默认 "auto"
        operation: (内部使用) 系统 Shell 操作依赖注入对象

    Returns:
        包含 success (bool), exit_code (int), output (str) 以及 optional error (str) 的字典
    """
    command = command.strip()
    if not command:
        return {"success": False, "exit_code": -1, "output": "", "error": "command cannot be empty"}

    if workdir and not os.path.isdir(workdir):
        return {"success": False, "exit_code": -1, "output": "", "error": f"workdir does not exist: {workdir}"}

    # 1. 后台执行分支
    if run_in_background:
        res = await operation.shell().execute_cmd_background(
            command, cwd=workdir or None, shell_type=shell_type
        )
        if res.code != 0:
            return {"success": False, "exit_code": -1, "output": "", "error": res.message}
        return {
            "success": True,
            "exit_code": 0,
            "output": f"Process started in background with PID: {res.data.pid}",
            "pid": res.data.pid,
        }

    # 2. 同步执行分支
    res = await operation.shell().execute_cmd(
        command, cwd=workdir or None, timeout=timeout, shell_type=shell_type
    )

    if res.code != 0:
        return {"success": False, "exit_code": -1, "output": "", "error": res.message}

    exit_code = res.data.exit_code if res.data else -1
    stdout = (res.data.stdout or "") if res.data else ""
    stderr = (res.data.stderr or "") if res.data else ""

    is_success = (exit_code == 0)
    output_text = stdout if is_success else (stderr or stdout)

    return {
        "success": is_success,
        "exit_code": exit_code,
        "output": output_text,
        "error": None if is_success else output_text,
    }
