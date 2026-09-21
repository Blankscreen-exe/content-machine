"""The rules every managed list shares: unique names, turning off instead of deleting what is used."""
from __future__ import annotations

import pytest
from sqlmodel import Session

from cm import choices, crud
from cm.models import Mode, PieceType, Platform
from helpers import mode_id


def test_names_are_unique_ignoring_case_and_spacing(session: Session):
    choices.create(session, Platform, "LinkedIn")
    with pytest.raises(choices.ChoiceError, match="already one called LinkedIn"):
        choices.create(session, Platform, "  linkedin ")


def test_a_blank_name_is_refused(session: Session):
    with pytest.raises(choices.ChoiceError, match="name is needed"):
        choices.create(session, Platform, "   ")


def test_renaming_to_its_own_name_is_fine_but_not_to_another(session: Session):
    newsletter = choices.create(session, Platform, "newsletter")
    choices.create(session, Platform, "blog")

    choices.update(session, newsletter, name="Newsletter")
    assert newsletter.name == "Newsletter"
    with pytest.raises(choices.ChoiceError):
        choices.update(session, newsletter, name="BLOG")


def test_modes_are_unique_per_brand_only(session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    choices.create(session, Mode, "advisor", brand_id=brand.id)
    choices.create(session, Mode, "advisor", brand_id=other.id)       # a different brand's
    with pytest.raises(choices.ChoiceError):
        choices.create(session, Mode, "Advisor", brand_id=brand.id)


def test_lists_are_alphabetical(session: Session):
    for name in ("x post", "Blog", "carousel"):
        choices.create(session, Platform, name)
    assert [p.name for p in choices.all_items(session, Platform)] == ["Blog", "carousel", "x post"]


def test_a_turned_off_item_is_offered_only_where_it_is_already_chosen(session: Session):
    old = choices.create(session, Platform, "old forum", active=False)
    current = choices.create(session, Platform, "blog")

    assert choices.options(session, Platform) == [current]
    assert old in choices.options(session, Platform, current_id=old.id)


def test_an_item_in_use_cannot_be_deleted(session: Session, brand):
    blog = choices.by_name(session, PieceType, "blog")
    crud.create_piece(session, brand_id=brand.id, type_id=blog.id, title="A piece")

    with pytest.raises(choices.ChoiceError, match="used by 1 piece. Turn it off"):
        choices.delete(session, blog)
    assert choices.get(session, PieceType, blog.id) is not None


def test_an_unused_item_can_be_deleted(session: Session):
    unused = choices.create(session, Platform, "newsletter")
    choices.delete(session, unused)
    assert choices.by_name(session, Platform, "newsletter") is None


@pytest.mark.parametrize("name", ["blog", "notes.txt", "sub/blog.md", "../blog.md", ".md"])
def test_a_main_file_must_be_a_plain_markdown_name(session: Session, name):
    with pytest.raises(choices.ChoiceError, match="plain file name"):
        choices.create(session, PieceType, "thread", main_file=name)


def test_a_main_file_cannot_be_the_generated_brief(session: Session):
    with pytest.raises(choices.ChoiceError, match="written by the app"):
        choices.create(session, PieceType, "thread", main_file="brief.md")


def test_an_idea_cannot_use_another_brands_mode(session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    theirs = mode_id(session, other.id, "commentator")

    with pytest.raises(choices.ChoiceError, match="another brand"):
        crud.create_idea(session, brand_id=brand.id, title="Mine", mode_id=theirs)

    idea = crud.create_idea(session, brand_id=brand.id, title="Mine")
    with pytest.raises(choices.ChoiceError):
        crud.update_idea(session, idea, mode_id=theirs)


def test_a_broken_rule_reaches_the_page_as_a_readable_400(client, session: Session, brand):
    other = crud.create_brand(session, "acme", "Acme Co")
    response = client.post("/ideas", data={"brand_id": brand.id, "title": "Mine",
                                           "mode_id": mode_id(session, other.id, "commentator")})
    assert response.status_code == 400
    assert response.json()["detail"] == "That mode belongs to another brand."


def test_a_piece_keeps_its_type_when_the_type_is_turned_off(client, session: Session, brand):
    quote = choices.by_name(session, PieceType, "quote")
    piece = crud.create_piece(session, brand_id=brand.id, type_id=quote.id, title="A quote")
    choices.update(session, quote, active=False)

    form = client.get(f"/pieces/{piece.id}/form").text
    new_form = client.get(f"/pieces/new?brand_id={brand.id}").text

    assert f'<option value="{quote.id}" selected>quote</option>' in form
    assert f'value="{quote.id}"' not in new_form
