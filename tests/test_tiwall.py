import pytest
from conftest import fixture

from tiwall_mcp.events import jalali_to_iso

pytestmark = pytest.mark.anyio

TOOLS = {
    "tw_categories",
    "tw_events",
    "tw_popular",
    "tw_search",
    "tw_event",
    "tw_sessions",
    "tw_venues",
    "tw_venue",
    "tw_reviews",
}


def test_jalali_conversion():
    assert jalali_to_iso(1405, 9, 3) == "2026-11-24"  # matches the site's ld+json startDate for the same event
    assert jalali_to_iso(1403, 12, 30) == "2025-03-20"  # leap-year Esfand 30
    assert jalali_to_iso(1405, 1, 1) == "2026-03-21"


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name


async def test_events_filters_and_cards(client, site):
    site["/showcase"] = fixture("showcase.html")
    site["/api/v2/assistant/search"] = fixture("assistant.json")
    r = (
        await client.call_tool(
            "tw_events", {"category": "theater", "city": "تهران", "day": "2026-11-20", "order": "sale", "limit": 2}
        )
    ).structured_content
    q = site.calls[-1].url.params
    assert q["filters"] == "s:theater,city:2111,day:2026-11-20" and q["order"] == "sale"
    assert r["total"] == 5 and len(r["events"]) == 2  # archived tail is cut off
    e = r["events"][0]
    assert e["slug"] == "panah6" and e["title"] == "پناه" and e["kind"] == "نمایش"
    assert e["price_min"] == e["price_max"] == 90000 and e["time"] == "18:30"
    assert e["venue"] == "سالن تئاتر کوثر" and "آبان" in e["dates"]
    sold = (await client.call_tool("tw_events", {"limit": 60})).structured_content["events"][-1]
    assert sold["slug"] == "moonwalk" and sold["sold_out"] is True
    assert (sold["price_min"], sold["price_max"]) == (450000, 550000) and sold["rating"] > 0


async def test_events_bad_day_is_rejected(client, site):
    r = await client.call_tool("tw_events", {"day": "tomorrow"})
    assert r.is_error


async def test_event_detail(client, site):
    site["/p/baroot"] = fixture("event.html")
    r = (await client.call_tool("tw_event", {"slug": "baroot"})).structured_content
    assert r["title"] == "بادروبه‌های باروت" and r["venue_slug"] == "labkhand"
    assert r["start_date"] == "2026-11-24" and r["end_date"] == "2026-12-24"
    assert r["price_min"] == r["price_ld_toman"] == 750000
    assert r["people"]["نویسنده و کارگردان"].startswith("حمیدرضا")
    assert r["time_and_duration"].startswith("18:30")
    assert r["lat"] == 35.705562 and r["tags"]["شهر"] == ["تهران"]
    assert r["summary"].startswith("و شاید")


async def test_event_slug_is_validated(client, site):
    r = await client.call_tool("tw_event", {"slug": "../../etc"})
    assert r.is_error


async def test_sessions(client, site):
    site["/s/baroot"] = fixture("sessions.html")
    r = (await client.call_tool("tw_sessions", {"slug": "baroot"})).structured_content
    assert [s["date"] for s in r["sessions"]] == ["2026-11-24", "2026-11-25", "2026-11-26"]
    assert r["sessions"][0]["seats"] == "مانده دارد" and r["sessions"][0]["id"] == 648373
    assert r["price"] == {"price_min": 750000, "price_max": 750000}


async def test_venues_lookup_skips_unknown_kinds(client, site):
    site["/api/v2/assistant/search"] = fixture("assistant.json")
    r = (await client.call_tool("tw_venues", {"query": "لبخند"})).structured_content
    assert [(x["kind"], x["id"]) for x in r["results"]] == [
        ("venue", 24818),
        ("city", 2111),
    ]  # the person_id row is skipped
    assert r["results"][0]["lat"] == 35.705562


async def test_venue_page_then_events(client, site):
    site["/labkhand"] = fixture("venue.html")
    site["/showcase"] = fixture("showcase.html")
    r = (await client.call_tool("tw_venue", {"slug": "labkhand", "limit": 2})).structured_content
    assert r["venue_id"] == 24818 and r["name"] == "مجموعه تئاتر لبخند" and r["followers"] == 303
    assert "09019999863 (مجموعه)" in r["contacts"] and r["address"].startswith("تهران")
    assert site.calls[-1].url.params["filters"] == "venue:24818" and len(r["events"]) == 2


async def test_reviews(client, site):
    site["/p/korokodil8/tags/review"] = fixture("wall.html")
    r = (await client.call_tool("tw_reviews", {"slug": "korokodil8", "kind": "review", "limit": 2})).structured_content
    assert site.calls[-1].headers["x-requested-with"] == "XMLHttpRequest"
    assert r["rating"] == 4.0 and r["rating_count"] == 58 and r["stars"]["5"] == 34
    assert r["posts_shown"] == 2 and r["posts"][0]["buyer"] is True and r["posts"][0]["author"]
    assert all(len(p["text"]) <= 500 for p in r["posts"])


async def test_search_encodes_query(client, site):
    site["/search/باروت"] = fixture("showcase.html")
    r = (await client.call_tool("tw_search", {"query": "باروت"})).structured_content
    assert r["total"] == 5


async def test_http_error_message(client, site):
    r = await client.call_tool("tw_sessions", {"slug": "nope"})
    assert r.is_error
