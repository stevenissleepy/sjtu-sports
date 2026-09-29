"""Automatic jAccount login and reservation session renewal."""

import json
import os
import tempfile
import time

from dotenv import load_dotenv
from playwright.sync_api import Error, sync_playwright
import requests
from requests import RequestException

from sjtu_sports.utils.paths import AUTH_DIR, HOME, ensure_auth_dir

SPORTS_BASE = "https://sports.sjtu.edu.cn"
SPORTS_URL = SPORTS_BASE + "/pc/?locale=zh#/"
USER_URL = SPORTS_BASE + "/system/user/currentUser"
STATE_FILE = AUTH_DIR / "storage_state.json"
LOGIN_ATTEMPTS = 5
LOGIN_RESULT_TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"


def _write_state(context):
    ensure_auth_dir()
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=AUTH_DIR, delete=False) as file:
            name = file.name
            os.chmod(name, 0o600)
            json.dump(context.storage_state(), file, ensure_ascii=False, indent=2)
        os.replace(name, STATE_FILE)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _browser_logged_in(context):
    try:
        response = context.request.get(USER_URL, timeout=5000)
        user = response.json().get("data")
        return response.ok and isinstance(user, dict) and bool(user.get("loginName"))
    except (Error, OSError, ValueError, AttributeError):
        return False


def _recognize_captcha(page, ocr):
    captcha = page.locator("#captcha-img")
    captcha.wait_for(state="visible", timeout=10000)
    page.wait_for_function(
        "document.querySelector('#captcha-img').complete && "
        "document.querySelector('#captcha-img').naturalWidth > 0"
    )
    previous = None
    image = b""
    for frame in range(10):
        page.wait_for_timeout(250)
        image = captcha.screenshot()
        if frame >= 2 and image == previous:
            break
        previous = image
    return ocr.classification(image).strip()


def _login():
    load_dotenv(HOME / ".env")
    username = os.environ.get("JACCOUNT_USERNAME", "")
    password = os.environ.get("JACCOUNT_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("自动登录需要在 .env 中设置 JACCOUNT_USERNAME 和 JACCOUNT_PASSWORD")

    import ddddocr

    ocr = ddddocr.DdddOcr(show_ad=False)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(locale="zh-CN")
            page = context.new_page()
            for attempt in range(1, LOGIN_ATTEMPTS + 1):
                page.goto(SPORTS_URL, wait_until="domcontentloaded", timeout=30000)
                page.get_by_role("button", name="校内人员登录").click(timeout=15000)
                page.locator("#input-login-user").wait_for(timeout=15000)
                page.locator("#input-login-user").fill(username)
                page.locator("#input-login-pass").fill(password)
                code = _recognize_captcha(page, ocr)
                if len(code) not in (4, 5) or not code.isascii() or not code.isalpha():
                    print(f"第 {attempt} 次未能识别验证码，重试。", flush=True)
                    continue
                page.locator("#input-login-captcha").fill(code)
                page.locator("#submit-password-button").click()
                deadline = time.monotonic() + LOGIN_RESULT_TIMEOUT
                while time.monotonic() < deadline:
                    if _browser_logged_in(context):
                        _write_state(context)
                        print("登录态已自动更新。", flush=True)
                        return
                    page.wait_for_timeout(1000)
                print(f"第 {attempt} 次登录未通过验证，重试。", flush=True)
        finally:
            browser.close()
    raise RuntimeError("自动登录失败：请检查账号密码、验证码或学校要求的额外验证")


def _load_cookies(session):
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        cookies = [
            (cookie["name"], cookie["value"], cookie["domain"], cookie.get("path", "/"))
            for cookie in state["cookies"]
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    session.cookies.clear()
    for name, value, domain, path in cookies:
        session.cookies.set(name, value, domain=domain, path=path)
    return True


def _session_logged_in(session):
    try:
        response = session.get(USER_URL, timeout=8)
    except RequestException as exc:
        raise RuntimeError("无法检查体育预约登录态，请检查网络或服务器状态") from exc
    if response.status_code in (401, 403) or "jaccount.sjtu.edu.cn" in response.url:
        return False
    if not response.ok:
        raise RuntimeError(f"无法检查体育预约登录态：HTTP {response.status_code}")
    try:
        user = response.json().get("data")
    except (ValueError, AttributeError):
        return False
    return isinstance(user, dict) and bool(user.get("loginName"))


def ensure_authenticated(session, *, load_saved=False):
    """Ensure the requests session is logged in; return True if it was renewed."""
    if load_saved and _load_cookies(session) and _session_logged_in(session):
        return False
    if not load_saved and _session_logged_in(session):
        return False

    print("登录态缺失或已失效，正在自动登录...", flush=True)
    _login()
    if not _load_cookies(session) or not _session_logged_in(session):
        raise RuntimeError("自动登录完成后仍无法验证体育预约登录态")
    return True


def retry_read_after_login(session, operation):
    """Retry a failed read once if its failure revealed an expired session."""
    response = operation()
    if response.get("code") != 0 and not response.get("network_error"):
        if ensure_authenticated(session):
            return operation()
    return response


def make_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": SPORTS_BASE + "/pc/",
        }
    )
    ensure_authenticated(session, load_saved=True)
    return session
