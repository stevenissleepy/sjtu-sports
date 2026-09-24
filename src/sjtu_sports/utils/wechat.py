"""Send a single reservation notification to the user's WeChat."""

import requests


def send_serverchan(sendkey, title, description):
    """Return (sent, error) without exposing the SendKey in errors."""
    try:
        response = requests.post(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            data={"title": title, "desp": description},
            timeout=5,
        )
    except requests.RequestException:
        return False, "网络请求失败"

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    try:
        result = response.json()
    except ValueError:
        return False, "响应不是 JSON"
    if not isinstance(result, dict):
        return False, "响应格式不正确"
    if result.get("code") != 0:
        return False, f"接口返回 code={result.get('code')}"
    return True, ""
