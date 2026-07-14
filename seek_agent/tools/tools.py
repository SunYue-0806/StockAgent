import inspect
import json
from typing import Dict, Any, Callable, List

_GLOBAL_TOOLS_MAP: Dict[str, Callable] = {}
_GLOBAL_TOOLS_SCHEMA: List[Dict[str, Any]] = []


def tool(func: Callable):
    func_name = func.__name__
    doc = func.__doc__.strip() or ""

    signature = inspect.signature(func)

    properties = {}

    required = []

    for param_name, param in signature.parameters.items():
        if param_name == "self":
            continue

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }

        param_type = type_map.get(param.annotation, "string")

        properties[param_name] = {
            "type": param_type,
            "description": f"参数 {param_name}"
        }

        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    schema = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": doc.strip(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }

    _GLOBAL_TOOLS_MAP[func_name] = func
    _GLOBAL_TOOLS_SCHEMA.append(schema)

    print(f"📦 [全局工具注册] 成功加载工具: {func_name}")
    return func


def get_all_tools_schema() -> List[Dict[str, Any]]:
    """获取全局注册的所有工具的 JSON Schema 说明书（直接喂给大模型）"""
    return _GLOBAL_TOOLS_SCHEMA


def execute_tool(name: str, arguments_str: str) -> str:
    """
    安全执行全局池子中的工具。
    接收大模型传回的工具名和 JSON 参数字符串，返回执行结果字符串。
    """
    if name not in _GLOBAL_TOOLS_MAP:
        return f"错误：全局工具箱中未找到名为 '{name}' 的工具。"

    try:
        args = json.loads(arguments_str) if arguments_str else {}
        result = _GLOBAL_TOOLS_MAP[name](**args)
        return str(result)
    except Exception as e:
        return f"错误：执行全局工具 '{name}' 时发生异常: {str(e)}"
