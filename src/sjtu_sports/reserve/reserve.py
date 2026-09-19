import argparse
import json
import time
from datetime import datetime

import requests

from sjtu_sports.utils.paths import AUTH_DIR
from sjtu_sports.utils import crypto

BASE = "https://sports.sjtu.edu.cn"
STATE_FILE = AUTH_DIR / "storage_state.json"

PERIODS = [
    "07:00-08:00", "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
    "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00", "16:00-17:00",
    "17:00-18:00", "18:00-19:00", "19:00-20:00", "20:00-21:00", "21:00-22:00",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

UNAVAILABLE = {"-1", "-2", "-3"}

TENSION = {0: "正常", 1: "紧张", 2: "很紧张", 3: "非常紧张", 4: "很紧张(签退)"}

POLL_INTERVAL = 0.3
QUERY_TIMEOUT = (2.0, 10.0)
SUBMIT_TIMEOUT = 8.0

VENUE_CONFLICT_MARKERS = (
    "已被预订",
    "已被预定",
    "已被预约",
    "已被占用",
    "场地不可用",
    "场地已满",
    "请重新选择场地",
    "状态已发生变化",
    "already booked",
    "already reserved",
    "occupied",
)


def make_session():
    s = requests.Session()
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for c in state["cookies"]:
        s.cookies.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://sports.sjtu.edu.cn/pc/",
    })
    return s


def json_post(s, path, data, extra_headers=None, timeout=5.0):
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        r = s.post(
            BASE + path,
            data=data if isinstance(data, str) else None,
            json=None if isinstance(data, str) else data,
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"code": -1, "msg": str(exc), "network_error": True}
    r.encoding = "utf-8"
    try:
        result = r.json()
    except Exception:
        result = {"code": -1, "raw": r.text}
    result.setdefault("http_status", r.status_code)
    return result


def form_post(s, path, data):
    r = s.post(BASE + path, data=data,
               headers={"Content-Type": "application/x-www-form-urlencoded"})
    r.encoding = "utf-8"
    try:
        return r.json()
    except Exception:
        return {"code": -1, "raw": r.text}


def query_venue_types(s, venue_id):
    return form_post(s, "/manage/venue/queryVenueById", {"id": venue_id})


def query_venues(s):
    return form_post(s, "/manage/venue/list", {
        "venueName": "",
        "pageNum": 1,
        "pageSize": 100,
        "flag": 1,
    })


def resolve_venue(s, selector):
    """Resolve a venue name or id to the venue returned by the API."""
    response = query_venues(s)
    venues = response.get("rows") or []
    selector_folded = selector.casefold()
    matches = [
        venue for venue in venues
        if selector == venue.get("venueId")
        or selector == venue.get("venueName")
        or selector_folded == (venue.get("venueNameEn") or "").casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def query_date_id(s, venue_id, field_type_id, date_str):
    data = {"id": venue_id, "feildType": field_type_id, "date": date_str}
    return json_post(s, "/manage/fieldDetail/queryFieldReserveSituationIsFull", data)


def query_fields(s, venue_id, field_type_id, date_str, date_id, timeout=5.0):
    data = {"fieldType": field_type_id, "date": date_str,
            "venueId": venue_id, "dateId": date_id}
    return json_post(s, "/manage/fieldDetail/queryFieldSituation", data, timeout=timeout)


def confirm_order(s, body, tid=None, date_id=None, timeout=8.0, key=None, sid=None):
    key = key or crypto.get_key()
    ts = str(int(time.time() * 1000))
    headers = {
        "sid": sid or crypto.rsa_encrypt(key),
        "tim": crypto.rsa_encrypt(ts),
    }
    if tid:
        headers["tid"] = tid
        body = dict(body)
        body["dateId"] = date_id
    payload = crypto.aes_encrypt(json.dumps(body, ensure_ascii=False), key)
    return json_post(
        s,
        "/venue/personal/ConfirmOrder",
        payload,
        extra_headers=headers,
        timeout=timeout,
    )


def week_number(date_str):
    return str((datetime.strptime(date_str, "%Y-%m-%d").weekday() + 1) % 7)


def find_sport(motion_types, sport):
    for mt in motion_types:
        if mt["id"] == sport or mt["name"] == sport or mt["nameEn"] == sport:
            return mt
    return None


def is_venue_conflict(response):
    """Return whether the server explicitly reports a lost venue race."""
    message = str(
        response.get("msg")
        or response.get("message")
        or response.get("msgContent")
        or ""
    ).casefold()
    return any(marker.casefold() in message for marker in VENUE_CONFLICT_MARKERS)


def build_space(item, field, row_idx):
    space = {("venuePrice" if k == "price" else k): v for k, v in item.items()}
    space.update({
        "scheduleTime": PERIODS[row_idx],
        "subSitename": field["fieldName"],
        "subSiteId": field["fieldId"],
        "tensity": field["fieldDetailStatus"],
        "venueNum": 1,
        "status": 1,
    })
    return space


def grab(s, args, motion_type, date_id):
    target_period = PERIODS.index(args.time) if args.time else None
    base_body = {
        "venTypeId": motion_type["id"],
        "venueId": args.venue,
        "fieldType": motion_type["name"],
        "returnUrl": "https://sports.sjtu.edu.cn/#/paymentResult/1",
        "scheduleDate": args.date,
        "week": week_number(args.date),
        "tenSity": TENSION.get(int(motion_type.get("tension", 0)), "正常"),
    }
    next_poll = time.monotonic()
    failures = 0
    order_key = crypto.get_key()
    order_sid = crypto.rsa_encrypt(order_key)

    while True:
        delay = next_poll - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        request_started = time.monotonic()
        next_poll = request_started + POLL_INTERVAL

        resp = query_fields(
            s,
            args.venue,
            motion_type["id"],
            args.date,
            date_id,
            timeout=QUERY_TIMEOUT,
        )
        if resp.get("code") != 0:
            failures += 1
            message = resp.get("msg") or resp.get("raw") or "未知错误"
            if not args.wait:
                print("查询场地失败:", message)
                return
            if failures == 1 or failures % 10 == 0:
                print(f"查询暂时失败，继续等待（连续 {failures} 次）: {message}")
            continue

        failures = 0

        fields = resp["data"]
        conflict_count = 0
        if args.field:
            candidates = [f for f in fields if f["fieldName"] == args.field]
        else:
            candidates = fields

        for field in candidates:
            price_list = field.get("priceList") or []
            indexed_prices = (
                [(target_period, price_list[target_period])]
                if target_period is not None and target_period < len(price_list)
                else enumerate(price_list)
            )
            for idx, item in indexed_prices:
                if idx >= len(PERIODS):
                    continue
                status = str(item.get("status"))
                if status in UNAVAILABLE:
                    continue
                print(f"命中可用: {field['fieldName']} {PERIODS[idx]} (status={status}, price={item.get('price')})")

                space = build_space(item, field, idx)
                body = dict(base_body, spaces=[space])
                if args.dry_run:
                    print("DRY-RUN 请求体:")
                    print(json.dumps(body, ensure_ascii=False, indent=1))
                    return
                print("提交抢订...")
                r = confirm_order(
                    s,
                    body,
                    timeout=SUBMIT_TIMEOUT,
                    key=order_key,
                    sid=order_sid,
                )
                print("响应:", json.dumps(r, ensure_ascii=False))
                if r.get("network_error"):
                    print("提交结果未知，请先查询订单状态，不要立即重复提交。")
                    return
                if r.get("code") == 0:
                    return
                if r.get("code") == 1002:
                    print("触发滑块验证码 (code 1002)，纯 HTTP 脚本暂无法自动处理，请改用浏览器手动提交。")
                    return
                if is_venue_conflict(r):
                    conflict_count += 1
                    print("该场地已被其他用户占用，尝试同一时段的下一个场地...")
                    order_key = crypto.get_key()
                    order_sid = crypto.rsa_encrypt(order_key)
                    continue
                print("提交失败，错误不属于场地竞争，停止抢订。")
                return

        if conflict_count:
            if args.wait:
                print(f"本轮 {conflict_count} 个可用场地均竞争失败，重新查询...")
                continue
            print(f"本轮 {conflict_count} 个可用场地均已被其他用户占用。")
            return

        if not args.wait:
            print("目标时段暂无可用场地。")
            return


def list_venues_main():
    response = query_venues(make_session())
    venues = response.get("rows") or []
    if not venues:
        print("获取场馆列表失败:", response.get("msg") or response.get("msgContent") or response)
        return

    print("场馆:")
    for venue in venues:
        english_name = venue.get("venueNameEn") or ""
        campus = venue.get("campusName") or venue.get("campusNameEn") or ""
        print(f"  - {venue['venueName']} ({english_name}) id={venue['venueId']} 校区={campus}")


def list_sports_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--venue", required=True, help="场馆名称")
    args = parser.parse_args()

    session = make_session()
    venue = resolve_venue(session, args.venue)
    if not venue:
        print(f"未找到场馆「{args.venue}」，可用 list-venues 查看")
        return

    response = query_venue_types(session, venue["venueId"])
    if response.get("code") != 0:
        print("获取运动类型失败:", response.get("msg"))
        return

    venue_data = response.get("data") or {}
    motion_types = venue_data.get("motionTypes") or []
    print(f"运动类型（{venue['venueName']}）:")
    for motion_type in motion_types:
        tension = TENSION.get(int(motion_type.get("tension", 0)))
        print(
            f"  - {motion_type['name']} ({motion_type.get('nameEn', '')}) "
            f"id={motion_type['id']} 紧张度={tension}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", required=True, help="场馆名称，可用 list-venues 查看")
    ap.add_argument("--sport", required=True, help="运动类型名称或 id，可用 list-sports 查看")
    ap.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD")
    ap.add_argument("--time", default=None, help="目标时段如 13:00-14:00，不填则抢任意可用")
    ap.add_argument("--field", default=None, help="优先场地名，如 场地1")
    ap.add_argument("--dry-run", action="store_true", help="只查询并构造请求体，不真正提交")
    ap.add_argument("--wait", action="store_true", help="轮询等待目标时段变为可用")
    args = ap.parse_args()

    if args.time and args.time not in PERIODS:
        ap.error(f"--time 必须是有效整点时段，例如 {PERIODS[0]}")

    s = make_session()
    venue = resolve_venue(s, args.venue)
    if not venue:
        print(f"未找到场馆「{args.venue}」，可用 list-venues 查看")
        return
    args.venue = venue["venueId"]

    resp = query_venue_types(s, args.venue)
    if resp.get("code") != 0:
        print("获取场馆信息失败，可能 cookie 已过期，请重新运行 save_login.py:", resp.get("msg"))
        return
    motion_types = resp["data"].get("motionTypes") or []

    motion_type = find_sport(motion_types, args.sport)
    if not motion_type:
        print(f"未找到运动类型「{args.sport}」，可用 list-sports 查看")
        return

    if not args.date:
        print("请提供 --date")
        return

    r = query_date_id(s, args.venue, motion_type["id"], datetime.now().strftime("%Y-%m-%d"))
    if r.get("code") != 0 or not r.get("data"):
        print("查询日期失败:", r.get("msg"))
        return
    date_entry = next((d for d in r["data"] if d.get("date") == args.date), None)
    if not date_entry:
        print(f"目标日期 {args.date} 不在可预订范围: {', '.join(d['date'] for d in r['data'])}")
        return
    date_id = date_entry["dateId"]

    grab(s, args, motion_type, date_id)


if __name__ == "__main__":
    main()
