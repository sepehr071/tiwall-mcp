import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def _first_slug(client):
    r = (await client.call_tool("tw_events", {"category": "theater", "city": "تهران", "limit": 3})).structured_content
    assert r["total"] > 0
    return r["events"][0]["slug"]


async def test_live_categories(client):
    r = (await client.call_tool("tw_categories", {})).structured_content
    assert "theater" in r["categories"] and {"id": 2111, "name": "تهران"} in r["cities"]


async def test_live_event_sessions_reviews(client):
    slug = await _first_slug(client)
    e = (await client.call_tool("tw_event", {"slug": slug})).structured_content
    assert e["title"] and e["venue"] and e["start_date"]
    s = (await client.call_tool("tw_sessions", {"slug": slug})).structured_content
    assert s["sessions"] and s["sessions"][0]["date"].startswith("20")
    rv = (await client.call_tool("tw_reviews", {"slug": slug, "limit": 2})).structured_content
    assert rv["slug"] == slug


async def test_live_venue(client):
    v = (await client.call_tool("tw_venues", {"query": "لبخند", "limit": 3})).structured_content["results"]
    assert any(x["slug"] == "labkhand" for x in v)
    r = (await client.call_tool("tw_venue", {"slug": "labkhand", "limit": 3})).structured_content
    assert r["venue_id"] == 24818 and r["events"]


async def test_live_search_and_popular(client):
    r = (await client.call_tool("tw_search", {"query": "باروت"})).structured_content
    assert r["events"]
    p = (await client.call_tool("tw_popular", {"category": "music", "limit": 3})).structured_content
    assert p["events"]
