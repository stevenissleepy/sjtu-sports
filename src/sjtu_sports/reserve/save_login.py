"""登录一次并保存会话 cookie，供纯 HTTP 脚本复用；顺带捕获 ConfirmOrder 加密前的明文"""
import json

from sjtu_sports.utils.paths import ensure_auth_dir

from playwright.sync_api import sync_playwright

OUT = ensure_auth_dir()
URL = "https://sports.sjtu.edu.cn/pc/?locale=zh#/"
STATE_FILE = OUT / "storage_state.json"
COOKIE_FILE = OUT / "cookies.txt"
PLAINTEXT_FILE = OUT / "plaintext.json"
PROFILE_DIR = OUT / "browser-profile"

HOOK = """
window.__pw_captures = [];
(function(){
  function hook() {
    try {
      var app = document.querySelector('#app');
      if (app && app.__vue__) {
        var V = app.__vue__.constructor;
        if (V.prototype.Aes && !V.prototype.Aes.__hooked) {
          var orig = V.prototype.Aes.encrypt;
          V.prototype.Aes.encrypt = function(p, k) {
            window.__pw_captures.push({plaintext: p, key: k, ts: Date.now()});
            return orig.call(this, p, k);
          };
          V.prototype.Aes.__hooked = true;
        }
      }
    } catch(e) {}
  }
  setInterval(hook, 300);
})();
"""


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            locale="zh-CN",
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script(HOOK)
        last_state_json = None
        saved_this_run = False
        captured_this_run = False

        def save_state():
            nonlocal last_state_json, saved_this_run
            try:
                state = context.storage_state()
                state_json = json.dumps(state, ensure_ascii=False, indent=2)
                if state_json == last_state_json:
                    return
                STATE_FILE.write_text(state_json, encoding="utf-8")
                lines = ["# Netscape HTTP Cookie File"]
                for cookie in state["cookies"]:
                    domain = cookie["domain"]
                    flag = "TRUE" if domain.startswith(".") else "FALSE"
                    path = cookie.get("path", "/")
                    secure = "TRUE" if cookie.get("secure") else "FALSE"
                    expires_at = cookie.get("expires", -1)
                    expires = str(int(expires_at)) if expires_at and expires_at > 0 else "0"
                    lines.append("\t".join([
                        domain, flag, path, secure, expires,
                        cookie["name"], cookie["value"],
                    ]))
                COOKIE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
                last_state_json = state_json
                saved_this_run = True
            except Exception:
                pass

        def save_capture():
            nonlocal captured_this_run
            try:
                captures = page.evaluate("window.__pw_captures || []")
                if captures:
                    PLAINTEXT_FILE.write_text(
                        json.dumps(captures, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    captured_this_run = True
            except Exception:
                pass

        def on_response(response):
            if not response.url.startswith("https://sports.sjtu.edu.cn/"):
                return
            if response.request.resource_type in {"fetch", "xhr"}:
                save_state()
            if "ConfirmOrder" in response.url:
                save_capture()

        def on_navigation(frame):
            if frame == page.main_frame and "sports.sjtu.edu.cn" in frame.url:
                save_state()

        page.on("response", on_response)
        page.on("framenavigated", on_navigation)
        page.goto(URL, wait_until="domcontentloaded")
        save_state()
        print("浏览器已打开，请登录。完成后直接关闭浏览器窗口。")

        try:
            while context.pages:
                page.wait_for_timeout(1000)
        except Exception:
            pass

        if saved_this_run:
            print(f"已保存 cookie ->\n{COOKIE_FILE}\n{STATE_FILE}")
        else:
            print("本次未能保存登录态，请重新运行并完成登录。")
        if captured_this_run:
            print(f"捕获到明文 -> {PLAINTEXT_FILE}")
        else:
            print("本次未捕获到 ConfirmOrder 明文（若未点提交属正常）。")


if __name__ == "__main__":
    main()
