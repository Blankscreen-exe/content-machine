"""Making a piece from another: a LinkedIn post from a blog post, with a session to write it."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, terminals, workspace
from cm.app import create_app
from cm.database import get_session
from cm.settings import get_settings
from helpers import type_id

TEST_TOKEN = os.environ["CM_TOKEN"]      # set by conftest before anything is imported


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture(name="blog")
def blog_fixture(session: Session, brand):
    idea = crud.create_idea(session, brand_id=brand.id, title="Cheap decisions compound")
    return crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"),
                             title=idea.title, idea_id=idea.id)


@pytest.fixture(name="launches")
def launches_fixture(monkeypatch):
    calls = []
    monkeypatch.setattr(terminals, "open_terminal",
                        lambda cwd, title, command, key=None: calls.append(command) or ["fake"])
    monkeypatch.setattr(terminals, "claude_command", lambda prompt: ["claude", prompt])
    return calls


@pytest.fixture(name="local_client")
def local_client_fixture(session: Session):
    app = create_app(run_migrations=False)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app, cookies={"cm_token": TEST_TOKEN}, client=("127.0.0.1", 45678)) as client:
        yield client


def test_a_derived_piece_keeps_the_idea_and_title_and_points_back(session: Session, blog):
    post = crud.derive_piece(session, blog, type_id(session, "linkedin post"))

    assert (post.title, post.idea_id, post.brand_id) == (blog.title, blog.idea_id, blog.brand_id)
    assert post.source_piece_id == blog.id
    assert workspace.piece_folder(session, post) != workspace.piece_folder(session, blog)


def test_its_brief_names_the_draft_to_work_from(session: Session, blog):
    post = crud.derive_piece(session, blog, type_id(session, "linkedin post"))

    text = workspace.write_brief(session, post).read_text(encoding="utf-8")

    assert "## Made from" in text
    assert str(workspace.piece_folder(session, blog) / "blog.md") in text
    assert "Use the derive skill." in text
    assert "- Main draft: `linkedin.md`" in text
    assert "- Character limit: 3,000" in text


def test_on_this_machine_it_opens_a_session_with_the_derive_skill(local_client: TestClient,
                                                                  session: Session, blog, launches):
    response = local_client.post(f"/pieces/{blog.id}/derive",
                                 data={"type_id": type_id(session, "linkedin post")})

    made = [p for p in crud.list_pieces(session) if p.source_piece_id == blog.id]
    assert len(made) == 1
    assert f'href="/pieces/{made[0].id}"' in response.text and "Session opened" in response.text
    assert "derive skill" in launches[0][1]


def test_from_another_device_it_makes_the_piece_but_no_session(client: TestClient, session: Session,
                                                               blog, launches):
    response = client.post(f"/pieces/{blog.id}/derive", data={"type_id": type_id(session, "x post")})

    assert "Made" in response.text and "machine running the app" in response.text
    assert launches == []
    assert any(p.source_piece_id == blog.id for p in crud.list_pieces(session))


def test_the_form_offers_every_other_type(client: TestClient, session: Session, blog):
    page = client.get(f"/pieces/{blog.id}").text
    form = page[page.index('class="inline-form derive-form"'):page.index("</form>", page.index("derive-form"))]

    assert f'value="{type_id(session, "linkedin post")}"' in form
    assert f'value="{type_id(session, "blog")}"' not in form


def test_deleting_the_source_keeps_what_was_made_from_it(session: Session, blog):
    post = crud.derive_piece(session, blog, type_id(session, "linkedin post"))

    workspace.delete_piece(session, blog)

    session.refresh(post)
    assert post.source_piece_id is None
    assert "## Made from" not in workspace.write_brief(session, post).read_text(encoding="utf-8")
