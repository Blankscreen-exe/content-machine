"""Reading a video's frames file: what it gives, and that every mistake is named, not guessed at."""
from __future__ import annotations

import pytest

from cm import frames
from cm.formats import FORMATS

GOOD = """# Three habits for a tidy desk

Format: square
Captions: off

A note to myself: record this one in the morning.

## Hook (4s)
Script: A messy desk quietly steals your focus.
On screen: "A messy desk steals your focus"
Animation: words rise one by one

## Frame 2 — habit one
Script: One in, one out.
Something new lands on the desk,
something old leaves.
On screen: big "01"

## Logo (2.5s)
On screen: the wordmark
"""


def _problems(text: str) -> list[str]:
    with pytest.raises(frames.FramesError) as caught:
        frames.parse(text)
    return caught.value.problems


def test_a_frames_file_reads_as_settings_and_frames():
    read = frames.parse(GOOD)

    assert read.title == "Three habits for a tidy desk"
    assert read.format is FORMATS["square"] and read.captions is False
    assert [f.title for f in read.frames] == ["Hook", "Frame 2 — habit one", "Logo"]
    assert [f.seconds for f in read.frames] == [4.0, None, 2.5]
    assert read.frames[0].animation == "words rise one by one"
    assert read.frames[2].script == "" and read.frames[2].on_screen == "the wordmark"


def test_a_line_without_a_field_carries_on_the_one_above():
    script = frames.parse(GOOD).frames[1].script
    assert script == "One in, one out.\nSomething new lands on the desk,\nsomething old leaves."


def test_settings_left_out_mean_vertical_with_captions():
    read = frames.parse("## Hook\nScript: Hello.")
    assert read.format is FORMATS["vertical"] and read.captions is True


def test_the_summary_says_what_will_be_made():
    assert frames.parse(GOOD).summary() == "3 frames · square 1080×1080 · captions off"


def test_every_problem_is_reported_at_once_with_where_it_is():
    problems = _problems("""Format: tall
Captions: maybe

## Hook
Just some words.
Script: Hello.
Script: Hello again.

## Silent
On screen: the logo
""")
    assert problems == [
        "Frame “Hook”, line 5: text before Script, On screen or Animation. Start the line with one of those.",
        "Frame “Hook”, line 7: Script appears twice.",
        "Format: “tall” is not one of vertical, square, portrait, landscape.",
        "Captions: “maybe” should be on or off.",
        "Frame “Silent” has no script, so give it a length, like (3s), at the end of its heading.",
    ]


def test_a_file_with_no_frames_says_how_to_start_one():
    assert _problems("# Title\n\nFormat: vertical\n") == [
        "No frames yet. Each frame starts with a heading: ## Title"]


def test_a_setting_given_twice_is_reported():
    assert _problems("Format: vertical\nFormat: square\n## Hook\nScript: Hi.") == [
        "Line 2: Format is set twice."]


def test_a_zero_length_frame_is_refused():
    assert _problems("## Pause (0s)\nScript: Hi.") == [
        "Frame “Pause” is 0 seconds long. Give it a length above zero, or none."]


def test_the_template_reads_as_frames():
    read = frames.parse(frames.template())
    assert read.format is FORMATS["vertical"] and read.captions
    assert [f.title for f in read.frames] == ["Hook", "[The point]", "Close"]
