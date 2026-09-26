"""Captions timed to the voice: the script's words, placed at the moments they are said."""
from __future__ import annotations

import pytest

from cm import captions
from cm.whisper import Heard


def heard(*pairs) -> list[Heard]:
    return [Heard(text, at) for text, at in pairs]


def test_words_heard_as_written_take_their_moments():
    times = captions.when_said(["You", "built", "a", "prototype."],
                               heard(("You", 0.6), ("built", 0.8), ("a", 1.0), ("prototype.", 1.4)))
    assert times == [0.6, 0.8, 1.0, 1.4]


def test_punctuation_case_and_hyphens_do_not_stop_a_match():
    times = captions.when_said(["AI-generated", "prototypes,"], heard(("ai-generated", 2.0), ("Prototypes", 2.6)))
    assert times == [2.0, 2.6]


def test_a_misheard_word_is_placed_between_its_neighbours():
    # the script says "hold"; whisper heard "go"
    times = captions.when_said(["parts", "that", "won't", "hold."],
                               heard(("parts", 10.0), ("that", 10.2), ("won't", 10.4), ("go.", 10.8)))
    assert times[:3] == [10.0, 10.2, 10.4]
    assert times[3] == pytest.approx(10.4 + captions.GAP)       # after the last heard, a word's length on


def test_a_word_said_but_not_in_the_script_does_not_shift_the_rest():
    times = captions.when_said(["I", "audit", "it", "and", "understand"],
                               heard(("I", 1.0), ("audit", 1.2), ("it", 1.5), ("and", 1.8), ("then", 2.0),
                                     ("understand", 2.3)))
    assert times == [1.0, 1.2, 1.5, 1.8, 2.3]


def test_unheard_words_inside_the_script_are_spread_between_heard_ones():
    times = captions.when_said(["one", "two", "three", "four"], heard(("one", 1.0), ("four", 4.0)))
    assert times == [1.0, 2.0, 3.0, 4.0]


def test_unheard_words_at_the_start_come_before_the_first_heard_one_never_below_zero():
    times = captions.when_said(["so", "then", "hello"], heard(("hello", 0.5)))
    assert times == pytest.approx([0.0, 0.5 - captions.GAP, 0.5])       # 0.5 - 2 gaps would be below zero


def test_a_take_with_none_of_the_script_in_it_gives_nothing_to_time_by():
    assert captions.when_said(["hello", "there"], heard(("completely", 1.0), ("different", 1.5))) is None
    assert captions.when_said(["hello"], []) is None


def test_times_never_go_backwards():
    times = captions.when_said(["a", "b", "a", "c"], heard(("a", 3.0), ("b", 1.0), ("c", 2.0)))
    assert times == sorted(times)


# --- onto the video's timeline -------------------------------------------------------------

SCENES = [
    {"from": 0, "duration": 60, "script": "Hello there."},
    {"from": 60, "duration": 60, "script": ""},
    {"from": 120, "duration": 30, "script": "Bye now."},
]
SAID = heard(("Hello", 0.5), ("there.", 1.0), ("Bye", 4.2), ("now.", 4.6))


def test_each_scene_gets_its_own_words_in_frames_from_its_start():
    placed = captions.timed_scenes(SCENES, SAID, {"from": 0, "trimBefore": 0}, fps=30)
    assert placed[0] == [{"text": "Hello", "from": 15, "to": 30}, {"text": "there.", "from": 30, "to": 60}]
    assert placed[1] is None                                    # nothing said in it
    assert placed[2] == [{"text": "Bye", "from": 6, "to": 18}, {"text": "now.", "from": 18, "to": 30}]


def test_the_take_is_placed_as_the_render_places_it():
    # started a second late (from 30) with its first half-second trimmed (trimBefore 15)
    placed = captions.timed_scenes(SCENES[:1], SAID[:2], {"from": 30, "trimBefore": 15}, fps=30)
    assert [w["from"] for w in placed[0]] == [30, 45]


def test_a_word_said_after_its_picture_has_gone_keeps_its_moment():
    """Captions follow the voice: the last word of a line often lands just after the cut."""
    late = heard(("Hello", 1.5), ("there.", 2.1), ("Bye", 4.2), ("now.", 4.6))
    placed = captions.timed_scenes(SCENES, late, {"from": 0, "trimBefore": 0}, fps=30)
    assert [w["from"] for w in placed[0]] == [45, 63]           # "there." is said at frame 63, after 60
    assert placed[0][-1]["to"] == 64


def test_without_anything_heard_every_scene_is_left_to_spread_its_script():
    assert captions.timed_scenes(SCENES, [], {"from": 0, "trimBefore": 0}, fps=30) == [None, None, None]


# --- kept beside the take ------------------------------------------------------------------

def test_what_was_heard_is_kept_beside_the_take(tmp_path):
    take = tmp_path / "take-4.webm"
    captions.save(take, SAID)
    assert captions.heard_path(take).name == "take-4.words.json"
    assert captions.load(take) == SAID


def test_what_another_model_heard_is_heard_again(tmp_path, monkeypatch):
    take = tmp_path / "take-4.webm"
    captions.save(take, SAID)
    monkeypatch.setattr(captions, "MODEL", "small.en")
    assert captions.load(take) is None
