import json

from sjtu_sports.utils.paths import ensure_output_dir

from playwright.sync_api import sync_playwright

URL = "https://sports.sjtu.edu.cn/pc/?locale=zh#/"
OUT = ensure_output_dir() / "captured.json"

records = []


def dump():
    try:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存失败:", e)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="zh-CN")
        page = context.new_page()

        def on_response(response):
            req = response.request
            if req.resource_type not in ("fetch", "xhr"):
                return
            try:
                body = response.text()
            except Exception:
                body = None
            entry = {
                "method": req.method,
                "url": req.url,
                "request_headers": dict(req.headers),
                "post_data": req.post_data,
                "status": response.status,
                "response_headers": dict(response.headers),
                "response_body": body,
            }
            records.append(entry)
            dump()
            print(f"[{len(records)}] {req.method} {response.status} {req.url}")

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded")
        print("浏览器已打开。请登录并完整走一遍抢订流程（查场地 -> 选时段 -> 提交抢订）。")
        print("完成后直接关闭浏览器窗口即可，数据会保存在 captured.json。")

        try:
            while browser.is_connected():
                page.wait_for_timeout(1000)
        except Exception:
            pass
        finally:
            dump()
            print(f"\n完成，共捕获 {len(records)} 条接口请求 -> {OUT}")


if __name__ == "__main__":
    main()
