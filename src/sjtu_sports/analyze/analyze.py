import json

from sjtu_sports.utils.paths import OUTPUT_DIR

skip = ["amap.com", "vdata"]

def short_body(s, n=400):
    if s is None:
        return None
    s = s.strip()
    return s[:n] + ("..." if len(s) > n else "")

def main():
    with (OUTPUT_DIR / "captured.json").open(encoding="utf-8") as capture_file:
        data = json.load(capture_file)

    print("=" * 80)
    print("请求清单（去噪）")
    print("=" * 80)
    for i, entry in enumerate(data):
        url = entry["url"]
        if any(item in url for item in skip):
            continue
        print(f"[{i}] {entry['method']} {entry['status']} {url}")

    print()
    print("=" * 80)
    print("关键请求详情")
    print("=" * 80)
    keys = ["currentUser", "captcha", "ConfirmOrder", "queryFieldSituation",
            "queryFieldReserveSituationIsFull", "ulogin", "queryOrder"]
    for entry in data:
        url = entry["url"]
        if any(key in url for key in keys):
            print()
            print("-" * 80)
            print(f"{entry['method']} {entry['status']} {url}")
            print("-" * 80)
            headers = entry.get("request_headers") or {}
            for key in ("cookie", "token", "authorization", "content-type", "x-token"):
                for header, value in headers.items():
                    if key in header.lower():
                        print(f"  REQ HEADER {header}: {value[:200]}")
            if entry.get("post_data"):
                print(f"  POST DATA: {entry['post_data'][:500]}")
            response_body = entry.get("response_body")
            if response_body:
                print(f"  RESP BODY: {short_body(response_body)}")


if __name__ == "__main__":
    main()
