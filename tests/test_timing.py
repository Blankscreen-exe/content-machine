"""How long each frame runs: the pace the voice is later recorded to."""
from __future__ import annotations

from cm import frames, timing
from cm.formats import FORMATS

TEN_WORDS = "one two three four five six seven eight nine ten"


def _line(text: str) -> timing.Timeline:
    return timing.timeline(frames.parse(text))


def test_a_frame_runs_as_long_as_its_script_takes_to_say_plus_a_breath():
    scene = _line(f"## Hook\nScript: {TEN_WORDS}").scenes[0]
    # ten words at 2.5 a second is 4 s; with the 0.4 s breath, 4.4 s at 30 frames a second
    assert (scene.length, scene.speech) == (132, 120)


def test_a_length_in_the_heading_is_kept_exactly():
    scene = _line(f"## Hook (3s)\nScript: {TEN_WORDS}").scenes[0]
    assert scene.length == 90
    assert scene.speech == 90            # said faster than usual, but never past the frame


def test_a_frame_with_almost_nothing_said_still_stays_long_enough_to_read():
    assert _line("## Hi\nScript: Hi.").scenes[0].length == round(timing.MIN_SECONDS * 30)


def test_a_silent_frame_has_no_speech():
    scene = _line("## Logo (2.5s)\nOn screen: the logo").scenes[0]
    assert (scene.length, scene.speech) == (75, 0)


def test_frames_follow_one_another_and_add_up():
    line = _line(f"## One (2s)\nScript: a\n## Two (3s)\nScript: b\n## Three\nScript: {TEN_WORDS}")
    assert [s.start for s in line.scenes] == [0, 60, 150]
    assert line.total == 60 + 90 + 132 and line.seconds == line.total / 30


def test_a_script_over_several_lines_is_counted_whole():
    scene = _line("## Hook\nScript: one two three four five\nsix seven eight nine ten").scenes[0]
    assert scene.speech == 120


def test_the_props_are_what_the_video_is_handed():
    props = timing.props(_line("Format: square\nCaptions: off\n\n## Hook (2s)\nScript: Hello there.\n"
                               "On screen: big hello\nAnimation: pops"))
    assert props == {
        "fps": 30, "width": FORMATS["square"].width, "height": FORMATS["square"].height,
        "total": 60, "captions": False,
        "scenes": [{"title": "Hook", "from": 0, "duration": 60, "speech": 24, "script": "Hello there.",
                    "onScreen": "big hello", "animation": "pops", "words": None}],
    }
