"""The Dashboard: what is due now, in progress, next up, and just published."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud
from cm.models import IdeaStatus, Stage
from helpers import platform_id, type_id


def _section(page: str, heading: str) -> str:
    start = page.index(f"<h2>{heading}</h2>")
    return page[start:page.index("</section>", start)]


def test_it_is_the_page_you_land_on(client: TestClient, brand):
    page = client.get("/").text
    assert 'href="/" class="on">Dashboard</a>' in page
    for heading in ("Due now", "In progress", "Next up", "Recently published"):
        assert f"<h2>{heading}</h2>" in page


def test_due_now_is_overdue_and_today_only(client: TestClient, session: Session, brand):
    blog, today = type_id(session, "blog"), date.today()
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Late", due_on=today - timedelta(days=2))
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Today", due_on=today)
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Friday", due_on=today + timedelta(days=3))

    due_now = _section(client.get("/").text, "Due now")

    assert ">Late</a>" in due_now and ">Today</a>" in due_now and "Friday" not in due_now
    assert 'class="overdue"' in due_now


def test_in_progress_leaves_out_unstarted_and_published_work(client: TestClient, session: Session, brand):
    blog = type_id(session, "blog")
    for title, stage in [("Drafting", Stage.draft), ("Nearly", Stage.ready),
                         ("Not yet", Stage.not_started), ("Out", Stage.published)]:
        crud.create_piece(session, brand_id=brand.id, type_id=blog, title=title, stage=stage)

    in_progress = _section(client.get("/").text, "In progress")

    assert ">Drafting</a>" in in_progress and ">Nearly</a>" in in_progress
    assert "Not yet" not in in_progress and ">Out</a>" not in in_progress


def test_next_up_is_pool_ideas_by_priority(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Someday", priority=3)
    crud.create_idea(session, brand_id=brand.id, title="Urgent", priority=1)
    crud.create_idea(session, brand_id=brand.id, title="Parked", priority=1, status=IdeaStatus.parked)

    next_up = _section(client.get("/").text, "Next up")

    assert next_up.index("Urgent") < next_up.index("Someday")
    assert "Parked" not in next_up


def test_recently_published_shows_the_platform(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Went out")
    crud.record_publication(session, piece, platform_id=platform_id(session, "newsletter"),
                            url="https://example.com/p")

    published = _section(client.get("/").text, "Recently published")

    assert ">Went out</a>" in published and "newsletter" in published


def test_everything_follows_the_brand_filter(client: TestClient, session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    blog = type_id(session, "blog")
    crud.create_piece(session, brand_id=brand.id, type_id=blog, title="Mine", stage=Stage.draft)
    crud.create_piece(session, brand_id=other.id, type_id=blog, title="Theirs", stage=Stage.draft)

    page = client.get(f"/?brand_id={other.id}").text

    assert ">Theirs</a>" in page and ">Mine</a>" not in page


def test_an_empty_workspace_says_so_rather_than_showing_nothing(client: TestClient, brand):
    page = client.get("/").text
    assert "Nothing overdue or due today." in page and "The idea pool is empty." in page
