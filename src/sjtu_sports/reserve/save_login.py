"""登录一次并保存会话 cookie，供纯 HTTP 脚本复用。"""

import json

from playwright.sync_api import Error, sync_playwright

from sjtu_sports.utils.paths import ensure_auth_dir

OUT = ensure_auth_dir()
URL = "https://sports.sjtu.edu.cn/pc/?locale=zh#/"
STATE_FILE = OUT / "storage_state.json"
COOKIE_FILE = OUT / "cookies.txt"
USER_URL = "https://sports.sjtu.edu.cn/system/user/currentUser"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="zh-CN")
        saved_this_run = False

        def save_state():
            state = context.storage_state()
            STATE_FILE.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            lines = ["# Netscape HTTP Cookie File"]
            for cookie in state["cookies"]:
                domain = cookie["domain"]
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = cookie.get("path", "/")
                secure = "TRUE" if cookie.get("secure") else "FALSE"
                expires_at = cookie.get("expires", -1)
                expires = str(int(expires_at)) if expires_at and expires_at > 0 else "0"
                lines.append(
                    "\t".join(
                        [
                            domain,
                            flag,
                            path,
                            secure,
                            expires,
                            cookie["name"],
                            cookie["value"],
                        ]
                    )
                )
            COOKIE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        print("浏览器已打开，请登录。完成后直接关闭浏览器窗口。")

        while browser.is_connected() and context.pages:
            if not saved_this_run:
                try:
                    response = context.request.get(USER_URL, timeout=3000)
                    user = response.json().get("data")
                    if isinstance(user, dict) and user.get("loginName"):
                        save_state()
                        saved_this_run = True
                        print("检测到登录成功，登录态已保存。", flush=True)
                except Error, OSError, ValueError:
                    pass
            try:
                context.pages[0].wait_for_timeout(1000)
            except Error:
                pass

        if saved_this_run:
            print(f"已保存 cookie ->\n{COOKIE_FILE}\n{STATE_FILE}")
        else:
            print("本次未能保存登录态，请重新运行并完成登录。")


if __name__ == "__main__":
    main()
