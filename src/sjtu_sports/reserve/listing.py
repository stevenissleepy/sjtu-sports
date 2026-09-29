"""Venue and sport lookup commands used by the reservation workflow."""

import argparse

from sjtu_sports.utils.auth import SPORTS_BASE, make_session, retry_read_after_login

TENSION = {0: "正常", 1: "紧张", 2: "很紧张", 3: "非常紧张", 4: "很紧张(签退)"}


def form_post(session, path, data):
    response = session.post(
        SPORTS_BASE + path,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.encoding = "utf-8"
    try:
        return response.json()
    except ValueError:
        return {"code": -1, "raw": response.text}


def query_venue_types(session, venue_id):
    return retry_read_after_login(
        session, lambda: form_post(session, "/manage/venue/queryVenueById", {"id": venue_id})
    )


def query_venues(session):
    return retry_read_after_login(
        session,
        lambda: form_post(
            session,
            "/manage/venue/list",
            {"venueName": "", "pageNum": 1, "pageSize": 100, "flag": 1},
        ),
    )


def resolve_venue(session, selector):
    """Resolve a venue name or id to the venue returned by the API."""
    response = query_venues(session)
    venues = response.get("rows") or []
    selector_folded = selector.casefold()
    matches = [
        venue
        for venue in venues
        if selector == venue.get("venueId")
        or selector == venue.get("venueName")
        or selector_folded == (venue.get("venueNameEn") or "").casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def list_venues_main():
    response = query_venues(make_session())
    venues = response.get("rows") or []
    if not venues:
        print(
            "获取场馆列表失败:",
            response.get("msg") or response.get("msgContent") or response,
        )
        return

    print("场馆:")
    for venue in venues:
        english_name = venue.get("venueNameEn") or ""
        campus = venue.get("campusName") or venue.get("campusNameEn") or ""
        print(
            f"  - {venue['venueName']} ({english_name}) id={venue['venueId']} 校区={campus}"
        )


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
