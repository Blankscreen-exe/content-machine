"""The Manage tab: brands with their voice and profile, and the lists you pick from."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import choices, crud
from cm.files import digest
from cm.models import Mode, PieceType, Platform
from helpers import mode_id, type_id

SECTIONS = ("brands", "modes", "types", "platforms")


# --- the page -----------------------------------------------------------------------

def test_manage_opens_on_brands(client: TestClient):
    response = client.get("/manage", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/manage/brands"


@pytest.mark.parametrize("section", SECTIONS)
def test_every_section_has_the_sidebar_with_itself_selected(client: TestClient, brand, section):
    page = client.get(f"/manage/{section}").text
    assert 'class="manage-nav"' in page
    for other in SECTIONS:
        assert f'href="/manage/{other}"' in page
    assert f'href="/manage/{section}" class="on" aria-current="page"' in page


# --- brands -------------------------------------------------------------------------

def test_a_new_brand_starts_with_a_placeholder_voice_and_profile(client: TestClient, session: Session):
    response = client.post("/manage/brands", data={"slug": "acme-co", "name": "Acme Co"})

    assert response.status_code == 200 and "Acme Co" in response.text
    brand = crud.get_brand_by_slug(session, "acme-co")
    assert brand.voice.startswith("# Voice: Acme Co")
    assert brand.profile.startswith("# Brand: Acme Co")


@pytest.mark.parametrize("slug", ["Acme Co", "acme_co", "-acme", "acme/co"])
def test_a_slug_must_be_folder_safe(client: TestClient, session: Session, slug):
    response = client.post("/manage/brands", data={"slug": slug, "name": "Acme Co"})
    assert response.status_code == 400
    assert "lowercase letters, numbers and dashes" in response.json()["detail"]


def test_a_taken_slug_is_refused_not_ignored(client: TestClient, brand):
    response = client.post("/manage/brands", data={"slug": brand.slug, "name": "Another"})
    assert response.status_code == 400
    assert "already a brand" in response.json()["detail"]


def test_renaming_a_brand_keeps_its_slug(client: TestClient, session: Session, brand):
    client.post(f"/manage/brands/{brand.id}", data={"name": "  A   New Name "})
    session.refresh(brand)
    assert (brand.name, brand.slug) == ("A New Name", "personal")


def test_turning_a_brand_off_keeps_its_work(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="Still here")

    client.post(f"/manage/brands/{brand.id}/active", data={"active": "false"})

    session.refresh(brand)
    assert brand.active is False
    assert len(crud.list_ideas(session, brand_id=brand.id)) == 1
    assert f'<option value="{brand.id}"' not in client.get("/").text     # gone from the filter only


def test_the_brand_page_edits_voice_and_profile_without_image_uploads(client: TestClient,
                                                                      session: Session, brand):
    crud.update_brand(session, brand, voice="# Voice: Example Person")
    page = client.get(f"/manage/brands/{brand.id}").text

    assert "# Voice: Example Person" in page
    assert f'hx-get="/manage/brands/{brand.id}/text/profile"' in page
    assert "data-upload-url" not in page


def test_saving_the_voice_stores_it(client: TestClient, session: Session, brand):
    response = client.post(f"/manage/brands/{brand.id}/text/voice",
                           data={"text": "calm and plain", "fingerprint": digest(brand.voice)})

    assert "Saved" in response.text
    session.refresh(brand)
    assert brand.voice == "calm and plain"


def test_a_voice_changed_elsewhere_is_not_overwritten(client: TestClient, session: Session, brand):
    opened = digest(brand.voice)
    crud.update_brand(session, brand, voice="written in another tab")

    response = client.post(f"/manage/brands/{brand.id}/text/voice",
                           data={"text": "written here", "fingerprint": opened})

    assert "changed somewhere else" in response.text and "Save anyway" in response.text
    assert "written here" in response.text                   # what you typed is still on screen
    session.refresh(brand)
    assert brand.voice == "written in another tab"

    client.post(f"/manage/brands/{brand.id}/text/voice",
                data={"text": "written here", "fingerprint": opened, "force": "true"})
    session.refresh(brand)
    assert brand.voice == "written here"


def test_only_voice_and_profile_can_be_edited(client: TestClient, brand):
    assert client.get(f"/manage/brands/{brand.id}/text/slug").status_code == 422


# --- modes --------------------------------------------------------------------------

def test_modes_show_one_brand_at_a_time(client: TestClient, session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    mode_id(session, brand.id, "advisor")
    mode_id(session, other.id, "commentator")

    page = client.get(f"/manage/modes?brand_id={other.id}").text

    assert 'value="commentator"' in page and 'value="advisor"' not in page


def test_without_a_brand_chosen_the_first_brand_is_shown(client: TestClient, session: Session, brand):
    mode_id(session, brand.id, "advisor")
    assert 'value="advisor"' in client.get("/manage/modes").text


def test_the_add_form_starts_from_the_mode_questions(client: TestClient, brand):
    assert "The reader is" in client.get(f"/manage/modes?brand_id={brand.id}").text


def test_adding_and_editing_a_mode(client: TestClient, session: Session, brand):
    client.post("/manage/modes", data={"brand_id": brand.id, "name": "advisor",
                                       "description": "calm"})
    mode = choices.by_name(session, Mode, "advisor", brand.id)
    assert mode.description == "calm"

    client.post(f"/manage/modes/{mode.id}", data={"name": "adviser", "description": "calmer"})
    session.refresh(mode)
    assert (mode.name, mode.description) == ("adviser", "calmer")


def test_a_mode_in_use_offers_only_to_be_turned_off(client: TestClient, session: Session, brand):
    used = mode_id(session, brand.id, "advisor")
    crud.create_idea(session, brand_id=brand.id, title="Uses it", mode_id=used)

    page = client.get(f"/manage/modes?brand_id={brand.id}").text
    assert "used by 1" in page
    assert f'/manage/modes/{used}/delete' not in page

    assert client.post(f"/manage/modes/{used}/delete").status_code == 400
    client.post(f"/manage/modes/{used}/active", data={"active": "false"})
    assert choices.get(session, Mode, used).active is False


# --- piece types and platforms -------------------------------------------------------

def test_adding_a_type_checks_its_main_file(client: TestClient, session: Session):
    assert client.post("/manage/types", data={"name": "thread", "main_file": "thread"}).status_code == 400

    response = client.post("/manage/types", data={"name": "thread", "main_file": "thread.md"})
    assert response.status_code == 200 and 'value="thread.md"' in response.text


def test_renaming_a_type_moves_no_folders(client: TestClient, session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
                              title="Legacy systems")
    slug = piece.slug

    client.post(f"/manage/types/{piece.type_id}", data={"name": "article", "main_file": "blog.md"})

    session.refresh(piece)
    assert piece.type.name == "article" and piece.slug == slug


def test_a_type_that_is_off_is_no_longer_offered_for_new_pieces(client: TestClient, session: Session,
                                                                brand):
    quote = type_id(session, "quote")
    client.post(f"/manage/types/{quote}/active", data={"active": "false"})
    assert f'value="{quote}"' not in client.get(f"/pieces/new?brand_id={brand.id}").text


def test_platforms_can_be_added_renamed_and_deleted_while_unused(client: TestClient,
                                                                 session: Session):
    client.post("/manage/platforms", data={"name": "newsletter"})
    platform = choices.by_name(session, Platform, "newsletter")

    client.post(f"/manage/platforms/{platform.id}", data={"name": "Newsletter"})
    session.refresh(platform)
    assert platform.name == "Newsletter"

    client.post(f"/manage/platforms/{platform.id}/delete")
    assert choices.by_name(session, Platform, "newsletter") is None


def test_a_duplicate_name_is_reported(client: TestClient):
    client.post("/manage/platforms", data={"name": "newsletter"})
    response = client.post("/manage/platforms", data={"name": "Newsletter"})
    assert response.status_code == 400 and "already one called" in response.json()["detail"]


def test_types_are_listed_alphabetically(client: TestClient, session: Session):
    names = sorted((t.name for t in choices.all_items(session, PieceType)), key=str.lower)
    page = client.get("/manage/types").text

    positions = [page.index(f'value="{name}"') for name in names]
    assert positions == sorted(positions)


# --- modes where ideas use them --------------------------------------------------------

def test_an_ideas_form_offers_its_own_brands_modes(client: TestClient, session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    mine = mode_id(session, brand.id, "advisor")
    mode_id(session, other.id, "commentator")

    form = client.get(f"/ideas/new?brand_id={brand.id}").text

    assert f'<option value="{mine}"' in form and "commentator" not in form


def test_on_all_brands_the_mode_list_follows_the_brand_picked(client: TestClient, session: Session,
                                                             brand):
    mine = mode_id(session, brand.id, "advisor")

    form = client.get("/ideas/new?brand_id=").text
    assert 'hx-get="/ideas/mode-field"' in form and "Pick a brand to see its modes." in form

    field = client.get(f"/ideas/mode-field?brand_id={brand.id}").text
    assert f'<option value="{mine}"' in field


def test_the_idea_list_shows_the_mode_by_name(client: TestClient, session: Session, brand):
    crud.create_idea(session, brand_id=brand.id, title="An idea",
                     mode_id=mode_id(session, brand.id, "advisor"))
    assert ">advisor</td>" in client.get("/").text
