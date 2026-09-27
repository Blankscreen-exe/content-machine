"""What is said in a video, written out: a script to read from and subtitles to upload."""
from __future__ import annotations

from cm import script

PROPS = {
    "fps": 30, "width": 1080, "height": 1920, "total": 300, "captions": False,
    "scenes": [
        {"title": "Hook", "from": 0, "duration": 120, "speech": 90, "words": None,
         "script": "You built a prototype with AI, and it works. But will it survive production?"},
        {"title": "Logo", "from": 120, "duration": 60, "speech": 0, "words": None, "script": ""},
        {"title": "Close", "from": 180, "duration": 120, "speech": 60, "words": None,
         "script": "Book a free meeting."},
    ],
}


def test_times_read_as_minutes_and_seconds():
    assert script.clock(0, 30) == "0:00.0" and script.clock(216, 30) == "0:07.2" and script.clock(1950, 30) == "1:05.0"
    assert script._srt_time(216, 30) == "00:00:07,200" and script._srt_time(108_000, 30) == "01:00:00,000"


def test_subtitle_lines_fit_a_phone_and_cover_the_scene_s_speech():
    cues = script.cues(PROPS)
    assert all(len(text) <= script.CUE_CHARS for _, _, text in cues)
    hook = [c for c in cues if c[0] < 120]
    assert " ".join(text for _, _, text in hook) == PROPS["scenes"][0]["script"]
    assert hook[0][0] == 0 and hook[-1][1] == 90                  # from the scene's start to its speech's end
    assert all(start < end for start, end, _ in cues)
    assert cues[-1] == (180, 240, "Book a free meeting.")        # the silent logo frame has none


def test_subtitles_follow_the_voice_when_the_captions_are_timed_to_a_take():
    timed = {**PROPS, "scenes": [{**PROPS["scenes"][2], "words": [
        {"text": "Book", "from": 12, "to": 20}, {"text": "a", "from": 20, "to": 24},
        {"text": "free", "from": 24, "to": 33}, {"text": "meeting.", "from": 33, "to": 55}]}]}
    assert script.cues(timed) == [(192, 235, "Book a free meeting.")]


def test_the_srt_is_numbered_cues_in_the_standard_form():
    lines = script.srt(PROPS).splitlines()
    assert lines[:3] == ["1", "00:00:00,000 --> 00:00:01,700", "You built a prototype with AI, and it"]
    assert "00:00:06,000 --> 00:00:08,000" in lines and "Book a free meeting." in lines


def test_the_script_says_what_to_say_and_by_when():
    text = script.script(PROPS, "AI prototype to production")
    assert text.startswith("# Script: AI prototype to production")
    assert "## 0:00.0 · Hook" in text and "_Said by 0:03.0; the frame runs to 0:04.0._" in text
    assert "## 0:04.0 · Logo" in text and "_Nothing said; the frame runs to 0:06.0._" in text
    assert "10.0 seconds · 1080×1920 · 3 frames, 2 with words" in text


def test_both_files_are_written_where_they_belong(tmp_path):
    script_path, captions_path = script.write(PROPS, "A short", tmp_path, tmp_path / "assets")
    assert script_path == tmp_path / "script.md" and captions_path == tmp_path / "assets" / "captions.srt"
    assert captions_path.read_text(encoding="utf-8").startswith("1\n00:00:00,000")
