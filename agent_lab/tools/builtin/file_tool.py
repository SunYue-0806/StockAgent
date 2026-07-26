import re
import subprocess
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from agent_lab.tools.tool_manager import tool

# --- 配置常量 ---
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1 GiB
MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5 MiB
MAX_TOKENS = 25_000
MAX_SIZE_BYTES = 256 * 1024  # 256 KB


@tool
def read_file(file_path: str, offset: int = 0, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    读取普通文本文件的指定行范围，并返回带行号的内容。

    Args:
        file_path: 文件路径
        offset: 跳过的行数 (从0开始)
        limit: 读取的最大行数 (None 表示读到文件末尾)

    Returns:
        包含操作状态、内容、行数等信息的字典
    """

    # 1. 基础检查
    if not os.path.exists(file_path):
        return {"success": False, "error": "File not found"}

    # 简单排除常见二进制文件
    binary_exts = {".pdf", ".doc", ".docx", ".zip", ".jpg", ".png", ".exe"}
    _, ext = os.path.splitext(file_path.lower())
    if ext in binary_exts:
        return {"success": False, "error": "Binary file type is not supported"}

    try:
        # 2. 逐行读取，节省内存
        selected_lines = []
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                if i < offset:
                    continue
                if limit is not None and len(selected_lines) >= limit:
                    break
                selected_lines.append(line.rstrip('\n'))

        # 3. 组装带行号的内容
        numbered_content = "\n".join(
            f"{i + offset + 1}\t{line}" for i, line in enumerate(selected_lines)
        )

        # 4. 安全检查
        content_bytes = numbered_content.encode('utf-8')
        if len(content_bytes) > MAX_SIZE_BYTES:
            return {
                "success": False,
                "error": f"Content size ({len(content_bytes) // 1024}KB) exceeds limit. Use 'limit' to read less."
            }

        # 简单估算 token 数量
        if len(numbered_content) // 4 > MAX_TOKENS:
            return {"success": False, "error": "Content exceeds token limit."}

        # 5. 返回结果
        return {
            "success": True,
            "content": numbered_content,
            "line_count": len(selected_lines),
            "file_path": file_path,
            "truncated": limit is not None and len(selected_lines) >= limit
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def write_file(file_path: str, content: str, expected_mtime: Optional[float] = None) -> Dict[str, Any]:
    """
    安全、原子化地写入普通文本文件。

    Args:
        file_path: 目标文件路径
        content: 要写入的文本内容
        expected_mtime: (可选) 预期修改时间 (Epoch 秒)。用于乐观锁校验，防止覆盖并发修改。

    Returns:
        包含操作状态、写入字节数、新 mtime 等信息的字典
    """

    # 1. 基础参数与类型检查
    if not isinstance(content, str):
        return {"success": False, "error": "content must be a string"}

    encoded_content = content.encode("utf-8", errors="replace")
    content_bytes = len(encoded_content)

    if content_bytes > MAX_CONTENT_SIZE:
        return {
            "success": False,
            "error": (
                f"Content is too large ({content_bytes / (1024 * 1024):.2f} MiB). "
                f"Maximum allowed is {MAX_CONTENT_SIZE // (1024 * 1024)} MiB."
            )
        }

    try:
        # 标准化绝对路径
        abs_path = os.path.abspath(file_path)
        dir_name = os.path.dirname(abs_path)

        # 2. 检查文件状态
        is_create = not os.path.exists(abs_path)

        if not is_create:
            if os.path.isdir(abs_path):
                return {"success": False, "error": f"Target path is a directory: {abs_path}"}

            stat = os.stat(abs_path)
            if stat.st_size > MAX_FILE_SIZE:
                return {"success": False,
                        "error": f"Existing file is too large ({stat.st_size / (1024 ** 3):.2f} GiB)."}

            # 3. 核心并发安全机制：mtime 校验（使用容差比较，避免浮点数精度损耗）
            if expected_mtime is not None:
                if abs(stat.st_mtime - expected_mtime) > 1e-3:
                    return {
                        "success": False,
                        "error": (
                            f"File has been modified since read (expected mtime: {expected_mtime}, "
                            f"actual mtime: {stat.st_mtime}). Please read the file again before writing."
                        )
                    }

        # 4. 自动创建所需目录
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        # 5. 原子写入：先写入同目录下的临时文件，然后使用 os.replace 替换
        # (确保写到一半报错时不会破坏原文件)
        temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_agent_")
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                f.write(content)

            # 原子替换原文件
            os.replace(temp_path, abs_path)
        except Exception:
            # 写入失败时清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

        # 6. 返回写入后的状态
        new_stat = os.stat(abs_path)
        return {
            "success": True,
            "file_path": abs_path,
            "bytes_written": content_bytes,
            "type": "create" if is_create else "update",
            "new_mtime": new_stat.st_mtime
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to write file: {str(e)}"}


@tool
def edit_file(file_path: str, new_content: str, expected_mtime: Optional[float] = None) -> Dict[str, Any]:
    """
    安全地编辑（覆盖写入）普通文本文件。

    Args:
        file_path: 文件路径
        new_content: 要写入的新文本内容
        expected_mtime: (可选) 预期修改时间。如果提供，写入前会校验文件是否被外部修改过。
                        通常通过 read_text_file 获取并传入。

    Returns:
        包含操作状态、写入字节数等信息的字典
    """

    # 1. 基础参数检查
    if not isinstance(new_content, str):
        return {"success": False, "error": "new_content must be a string"}

    content_bytes = len(new_content.encode("utf-8", errors="replace"))
    if content_bytes > MAX_CONTENT_SIZE:
        return {
            "success": False,
            "error": (
                f"Content is too large ({content_bytes // (1024 * 1024)} MiB). "
                f"Maximum allowed is {MAX_CONTENT_SIZE // (1024 * 1024)} MiB. "
                "Please use shell commands to write large files."
            )
        }

    try:
        # 2. 文件存在性及大小检查
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        if os.path.isdir(file_path):
            return {"success": False, "error": f"Target path is a directory: {file_path}"}

        stat = os.stat(file_path)
        if stat.st_size > MAX_FILE_SIZE:
            return {"success": False, "error": f"File is too large ({stat.st_size // (1024 ** 3)} GiB)."}

        # 3. 核心安全机制：防并发/防覆盖校验
        if expected_mtime is not None and stat.st_mtime != expected_mtime:
            return {
                "success": False,
                "error": (
                    "File has been modified since read. "
                    "Please read the file again before attempting to edit."
                )
            }

        # 4. 执行写入
        # 默认使用 utf-8 编码
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        # 5. 获取写入后的最新状态
        new_stat = os.stat(file_path)

        return {
            "success": True,
            "file_path": file_path,
            "bytes_written": len(new_content.encode('utf-8', errors='replace')),
            "type": "update",
            "new_mtime": new_stat.st_mtime  # 返回新的修改时间，方便下次编辑时校验
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def list_files(path: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
    """
    列出指定目录下的文件和子目录。

    Args:
        path: 目录路径，默认为当前目录 "."
        show_hidden: 是否显示隐藏文件（以 . 开头的文件）

    Returns:
        包含文件和目录列表的字典
    """
    try:
        if not os.path.exists(path):
            return {"success": False, "error": f"Path not found: {path}"}
        if not os.path.isdir(path):
            return {"success": False, "error": f"Path is not a directory: {path}"}

        all_entries = os.listdir(path)

        files: List[str] = []
        dirs: List[str] = []

        for entry in all_entries:
            if not show_hidden and entry.startswith('.'):
                continue

            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                dirs.append(entry)
            else:
                files.append(entry)

        files.sort()
        dirs.sort()

        return {
            "success": True,
            "path": os.path.abspath(path),
            "files": files,
            "dirs": dirs
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def grep(pattern: str, path: str = ".", glob: Optional[str] = None, ignore_case: bool = False,
         head_limit: Optional[int] = None) -> Dict[str, Any]:
    """
    在文件中搜索指定的文本模式。

    Args:
        pattern: 要搜索的文本模式
        path: 搜索的目录或文件路径
        glob: 可选的文件匹配模式，例如 "*.py"
        ignore_case: 是否忽略大小写
        head_limit: 限制返回的最大行数

    Returns:
        包含搜索结果、退出码等信息的字典
    """
    if not pattern:
        return {"success": False, "error": "pattern is required"}

    # 构建 grep 命令
    cmd = ["grep", "-R", "--color=never", "--binary-files=without-match"]

    if ignore_case:
        cmd.append("-i")

    if glob:
        cmd.extend(["--include", glob])

    cmd.extend([pattern, path])

    try:
        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        # 处理输出
        stdout_lines = result.stdout.splitlines()

        # 应用行数限制
        if head_limit is not None:
            stdout_lines = stdout_lines[:head_limit]

        content = "\n".join(stdout_lines)

        # grep 退出码 0 表示找到匹配，1 表示未找到，其他表示出错
        success = result.returncode in (0, 1)

        return {
            "success": success,
            "exit_code": result.returncode,
            "stdout": content,
            "stderr": result.stderr,
            "num_lines": len(stdout_lines),
            "error": result.stderr if not success else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def glob_files(pattern: str, path: str = ".", max_results: int = 100) -> Dict[str, Any]:
    """
    使用通配符模式搜索文件。

    Args:
        pattern: 文件匹配模式，例如 "*.py" 或 "*.{py,js}"
        path: 搜索的根目录
        max_results: 限制返回的最大文件数量

    Returns:
        包含匹配文件列表、搜索耗时等信息的字典
    """
    if not pattern:
        return {"success": False, "error": "pattern is required"}

    def expand_brace_pattern(pat: str) -> List[str]:
        """展开 shell 风格的大括号模式，如 *.{py,js} -> ['*.py', '*.js']"""
        if '{' not in pat or '}' not in pat:
            return [pat]

        match = re.search(r'\{([^{}]*)\}', pat)
        if not match:
            return [pat]

        prefix = pat[:match.start()]
        suffix = pat[match.end():]
        results = []
        for opt in match.group(1).split(','):
            results.extend(expand_brace_pattern(prefix + opt.strip() + suffix))
        return results

    try:
        start_time = time.perf_counter()
        search_path = Path(path).expanduser().resolve()

        if not search_path.exists():
            return {"success": False, "error": f"Path not found: {path}"}

        expanded_patterns = expand_brace_pattern(pattern)
        all_matching_files: List[str] = []
        seen: set = set()

        for pat in expanded_patterns:
            # 使用 rglob 进行递归搜索
            for file_path in search_path.rglob(pat):
                if file_path.is_file():
                    abs_path = str(file_path.resolve())
                    if abs_path not in seen:
                        seen.add(abs_path)
                        all_matching_files.append(abs_path)

        # 结果限制
        truncated = len(all_matching_files) > max_results
        limited_files = all_matching_files[:max_results]

        # 转换为相对路径
        relative_files = [os.path.relpath(p, search_path) for p in limited_files]

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "success": True,
            "durationMs": duration_ms,
            "numFiles": len(relative_files),
            "filenames": relative_files,
            "truncated": truncated,
            "count": len(relative_files),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
