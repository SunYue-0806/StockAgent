"""tools/weather_tool.py - 心知天气工具实现"""

import os
import requests

from seek_agent.tools.tools import tool

XIN_ZHI_WEATHER_API_KEY = os.getenv("XIN_ZHI_WEATHER_API_KEY", "你的心知天气私钥")


@tool
def get_current_weather(location: str) -> str:
    """
    获取指定城市当前的实时天气状况，包括天气现象文本（如晴、多云）、温度和最近更新时间。

    :param location: 城市名称，支持中文（如 "北京"、"上海"）、拼音、海外城市英文名或 IP 地址。
    """
    if not XIN_ZHI_WEATHER_API_KEY or XIN_ZHI_WEATHER_API_KEY == "你的心知天气私钥":
        return "错误：未配置心知天气的 API Key，请先在环境变量或代码中设置。"

    url = "https://api.seniverse.com/v3/weather/now.json"

    params = {
        "key": XIN_ZHI_WEATHER_API_KEY,
        "location": location,
        "language": "zh-Hans",
        "unit": "c"
    }
    response = None
    try:
        response = requests.get(url, params=params, timeout=5)

        response.raise_for_status()

        data = response.json()

        result = data["results"][0]
        city_name = result["location"]["name"]
        weather_now = result["now"]
        text = weather_now["text"]
        temperature = weather_now["temperature"]
        last_update = result["last_update"]

        return f"【心知天气】{city_name}当前天气：{text}，气温：{temperature}℃。（更新时间：{last_update}）"

    except requests.exceptions.HTTPError as http_err:
        try:
            err_data = response.json()
            err_msg = err_data.get("status", str(http_err))
            return f"天气接口调用失败：{err_msg}"
        except Exception:
            return f"天气接口调用失败，状态码: {response.status_code}"

    except Exception as e:
        return f"查询天气时发生未知错误: {str(e)}"
