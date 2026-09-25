"""A video's voice: takes are kept, choices are numbers that are checked, and a bad
mix.json is reported rather than lost."""
from __future__ import annotations

import io
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from cm import crud, renders, resources, video, voice, workspace
from cm.settings import get_settings
from helpers import type_id

WEBM = b"\x1aE\xdf\xa3 a recorded take"


@pytest.fixture(autouse=True)
def workspace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "workspace", tmp_path)
    return tmp_path


@pytest.fixture
def short(session: Session, brand):
    piece = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "youtube short"), title="A short")
    (workspace.ensure_folder(session, piece) / "frames.md").write_text(
        "## Hook (2s)\nScript: Hello there you.\n## Close (1s)\nScript: Bye.\n", encoding="utf-8")
    return piece


@pytest.fixture
def folder(session: Session, short):
    return workspace.piece_folder(session, short)


# --- takes -------------------------------------------------------------------------------

def test_takes_are_numbered_in_order_and_the_newest_is_used(folder):
    assert voice.save_take(folder, "blob.webm", io.BytesIO(WEBM)) == "take-1.webm"
    voice.write_mix(folder, voice.Mix(take="take-1.webm", offset=0.4, trim_start=1.0, music="theme.mp3"))

    assert voice.save_take(folder, "anything.m4a", io.BytesIO(b"m4a")) == "take-2.m4a"

    mix = voice.read_mix(folder)
    assert mix.take == "take-2.m4a" and (mix.offset, mix.trim_start) == (0.0, 0.0)   # lined up afresh
    assert mix.music == "theme.mp3"                                                     # the music stays
    assert [t.name for t in voice.takes(folder)] == ["take-1.webm", "take-2.m4a"]


def test_a_take_must_be_audio(folder):
    with pytest.raises(voice.assets.BadAsset, match="a take is one of"):
        voice.save_take(folder, "clip.mp4", io.BytesIO(b"video"))


def test_deleting_the_take_in_use_leaves_the_mix_without_one(folder, tmp_path):
    voice.save_take(folder, "take.webm", io.BytesIO(WEBM))
    voice.trash_take(folder, "take-1.webm", tmp_path / "trash")
    assert voice.read_mix(folder).take is None and (tmp_path / "trash" / "take-1.webm").exists()


# --- mix.json ----------------------------------------------------------------------------

def test_no_mix_yet_means_no_voice_and_no_music(folder):
    assert voice.read_mix(folder) == voice.Mix()


def test_a_mix_that_cannot_be_read_is_reported_and_left_alone(folder):
    path = voice.folder_of(folder) / voice.MIX_FILE
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(voice.MixError, match="it is not replaced automatically"):
        voice.read_mix(folder)
    assert path.read_text(encoding="utf-8") == "{not json"


def test_settings_it_does_not_know_are_reported(folder):
    path = voice.folder_of(folder) / voice.MIX_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"take": None, "reverb": 3}), encoding="utf-8")
    with pytest.raises(voice.MixError, match="does not know: reverb"):
        voice.read_mix(folder)


@pytest.mark.parametrize("mix, message", [
    (voice.Mix(offset=90), "offset should be a number from -60 to 60"),
    (voice.Mix(volume=-1), "volume should be a number from 0 to 2"),
    (voice.Mix(trim_start=5, trim_end=3), "trim_end (3s) should come after trim_start (5s)"),
    (voice.Mix(offset=-4, trim_end=3), "none of the take before trim_end (3s) is heard"),
])
def test_numbers_that_make_no_sense_are_refused(folder, mix, message):
    with pytest.raises(voice.MixError, match=message.replace("(", r"\(").replace(")", r"\)")):
        voice.write_mix(folder, mix)
    assert not (voice.folder_of(folder) / voice.MIX_FILE).exists()


def test_a_mix_is_written_whole(folder):
    voice.write_mix(folder, voice.Mix(take="take-1.webm", volume=1.2))
    assert [p.name for p in voice.folder_of(folder).iterdir()] == [voice.MIX_FILE]
    assert voice.read_mix(folder).volume == 1.2


# --- what a render is handed ---------------------------------------------------------------

def test_a_later_take_starts_later_and_a_trim_is_skipped():
    props = voice.props(voice.Mix(take="take-2.webm", offset=0.5, trim_start=1.0, trim_end=9.0, volume=0.9), fps=30)
    assert props["voice"] == {"src": "voice.webm", "from": 15, "trimBefore": 30, "trimAfter": 270, "volume": 0.9}
    assert props["music"] is None


def test_an_early_take_starts_at_once_with_its_start_skipped():
    props = voice.props(voice.Mix(take="take-1.m4a", offset=-0.5, trim_start=1.0), fps=30)
    assert props["voice"] == {"src": "voice.m4a", "from": 0, "trimBefore": 45, "trimAfter": None, "volume": 1.0}


def test_music_is_handed_over_by_its_role():
    props = voice.props(voice.Mix(music="Calm Pad.WAV", music_volume=0.2), fps=30)
    assert props == {"voice": None, "music": {"src": "music.wav", "volume": 0.2}}


def test_a_render_plan_carries_the_files_it_plays(session: Session, short, brand, folder):
    voice.save_take(folder, "take.webm", io.BytesIO(WEBM))
    music = resources.folder(brand.slug, "music")
    music.mkdir(parents=True)
    (music / "theme.mp3").write_bytes(b"ID3")
    voice.write_mix(folder, voice.Mix(take="take-1.webm", music="theme.mp3"))

    plan = renders.plan(session, short)

    assert plan.public == {"voice.webm": voice.folder_of(folder) / "take-1.webm", "music.mp3": music / "theme.mp3"}
    assert plan.props["voice"]["src"] == "voice.webm" and plan.props["music"]["src"] == "music.mp3"


def test_a_mix_naming_a_file_that_is_gone_stops_the_render(session: Session, short, folder):
    voice.write_mix(folder, voice.Mix(music="gone.mp3"))
    with pytest.raises(video.RenderError, match="no longer there"):
        renders.plan(session, short)


# --- the Voice page ------------------------------------------------------------------------

def test_the_page_says_to_render_a_draft_first(client: TestClient, short):
    page = client.get(f"/pieces/{short.id}/voice").text
    assert "There is no draft to record over yet." in page and 'id="studio-data"' in page


def test_the_page_warns_when_the_frames_changed_after_the_draft(client: TestClient, short, folder):
    draft = folder / "assets" / "draft.mp4"
    draft.write_bytes(b"mp4")
    frames_file = folder / "frames.md"
    os.utime(draft, (1_000_000, 1_000_000))
    page = client.get(f"/pieces/{short.id}/voice").text
    assert "has changed since the draft was rendered" in page and 'id="studio-video"' in page
    assert frames_file.stat().st_mtime > draft.stat().st_mtime


def test_recording_is_offered_only_at_a_loopback_address(local_client: TestClient, short, folder):
    """Browsers allow the microphone only on a secure address, which over http means loopback.
    The --lan link opened on this same machine comes from here, but still cannot record."""
    (folder / "assets" / "draft.mp4").write_bytes(b"mp4")
    for address in ("localhost:8777", "127.0.0.1:8777"):
        assert 'id="record" >' in local_client.get(f"http://{address}/pieces/{short.id}/voice").text
    lan = local_client.get(f"http://192.168.1.20:8777/pieces/{short.id}/voice").text
    assert 'id="record" disabled' in lan
    assert f"http://localhost:8777/pieces/{short.id}/voice" in lan      # says where to go instead


def test_the_teleprompter_is_handed_the_frames_as_saved(client: TestClient, short):
    page = client.get(f"/pieces/{short.id}/voice").text
    data = json.loads(page.split('id="studio-data">', 1)[1].split("</script>", 1)[0])
    assert [s["script"] for s in data["scenes"]] == ["Hello there you.", "Bye."]
    assert data["scenes"][1]["from"] == 60 and data["fps"] == 30


def test_an_uploaded_take_is_stored_and_served(client: TestClient, short, folder):
    response = client.post(f"/pieces/{short.id}/voice/takes", files={"take": ("take.webm", WEBM, "audio/webm")})
    assert response.json() == {"name": "take-1.webm"}

    served = client.get(f"/pieces/{short.id}/voice/takes/take-1.webm")
    assert served.content == WEBM and served.headers["content-type"] == "video/webm"
    assert client.get(f"/pieces/{short.id}/voice/takes/mix.json").status_code == 404


def test_saving_the_settings_comes_back_to_the_page(client: TestClient, short, folder):
    voice.save_take(folder, "take.webm", io.BytesIO(WEBM))
    response = client.post(f"/pieces/{short.id}/voice/mix", data={
        "take": "take-1.webm", "offset": "0.25", "trim_start": "0.5", "trim_end": "", "volume": "1.1",
        "music": "", "music_volume": "0.1"}, follow_redirects=False)

    assert response.status_code == 303 and response.headers["location"].endswith("/voice?saved=true")
    assert voice.read_mix(folder) == voice.Mix(take="take-1.webm", offset=0.25, trim_start=0.5, volume=1.1,
                                               music_volume=0.1)


@pytest.mark.parametrize("change, message", [
    ({"take": "take-9.webm"}, "There is no take called take-9.webm."),
    ({"music": "nothing.mp3"}, "The brand&#39;s music has no nothing.mp3."),
    ({"offset": "soon"}, "Offset should be a number, not &#39;soon&#39;."),
])
def test_settings_that_do_not_fit_are_explained_and_not_saved(client: TestClient, short, folder, change, message):
    form = {"take": "", "offset": "0", "trim_start": "0", "trim_end": "", "volume": "1", "music": "",
            "music_volume": "0.1"} | change
    page = client.post(f"/pieces/{short.id}/voice/mix", data=form).text
    assert message in page
    assert not (voice.folder_of(folder) / voice.MIX_FILE).exists()


def test_deleting_a_take_moves_it_to_the_trash(client: TestClient, short, brand, folder, workspace_dir):
    voice.save_take(folder, "take.webm", io.BytesIO(WEBM))
    response = client.post(f"/pieces/{short.id}/voice/takes/take-1.webm/delete", follow_redirects=False)
    assert response.status_code == 303
    assert (workspace_dir / "trash" / brand.slug / folder.name / "voice" / "take-1.webm").exists()


def test_a_text_piece_has_no_voice_page(client: TestClient, session: Session, brand):
    blog = crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="A post")
    assert client.get(f"/pieces/{blog.id}/voice").status_code == 400
