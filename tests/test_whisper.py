"""whisper.cpp: what it heard read back as words, and a download kept only if it is the one expected."""
from __future__ import annotations

import hashlib
import io

import pytest

from cm import whisper


def token(text: str, dtw: int, start_ms: int = 0) -> dict:
    return {"text": text, "t_dtw": dtw, "offsets": {"from": start_ms, "to": start_ms + 100}}


def test_tokens_are_joined_back_into_words_said_when_their_first_part_is():
    result = {"transcription": [
        {"tokens": [token("[_BEG_]", -1), token(" You", 62), token(" built", 84), token(" AI", 202),
                    token("-", 210), token("gener", 215), token("ated", 230), token(",", 240)]},
        {"tokens": [token(" works", 304), token("[_TT_150]", -1)]},
    ]}
    assert whisper.words(result) == [
        whisper.Heard("You", 0.62), whisper.Heard("built", 0.84), whisper.Heard("AI-generated,", 2.02),
        whisper.Heard("works", 3.04)]


def test_without_a_dtw_time_a_token_falls_back_to_where_its_text_starts():
    assert whisper.words({"transcription": [{"tokens": [token(" hello", -1, start_ms=1500)]}]}) == [
        whisper.Heard("hello", 1.5)]


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_a_download_is_kept_only_when_it_matches_its_checksum(tmp_path, monkeypatch):
    payload = b"the model"
    monkeypatch.setattr(whisper.urllib.request, "urlopen", lambda url, timeout, context: Response(payload))

    kept = whisper._download("https://example.invalid/model.bin", hashlib.sha256(payload).hexdigest(),
                             tmp_path / "model.bin")
    assert kept.read_bytes() == payload

    with pytest.raises(whisper.WhisperError, match="did not match its recorded checksum"):
        whisper._download("https://example.invalid/other.bin", "0" * 64, tmp_path / "other.bin")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["model.bin"]      # nothing half-kept


def test_a_download_that_fails_leaves_nothing_behind(tmp_path, monkeypatch):
    def offline(url, timeout, context):
        raise OSError("no route to host")
    monkeypatch.setattr(whisper.urllib.request, "urlopen", offline)
    with pytest.raises(whisper.WhisperError, match="Check the connection"):
        whisper._download("https://example.invalid/model.bin", "0" * 64, tmp_path / "model.bin")
    assert list(tmp_path.iterdir()) == []


def test_downloads_never_log_session_keys_whatever_the_environment_asks(monkeypatch):
    """Some antivirus sets SSLKEYLOGFILE to a pipe that crashes OpenSSL in some Python builds."""
    monkeypatch.setenv("SSLKEYLOGFILE", r"\.\someProxy\keys")
    context = whisper._tls()
    assert context.keylog_filename is None
    assert context.verify_mode == whisper.ssl.CERT_REQUIRED and context.check_hostname


@pytest.mark.parametrize("system, machine, archive", [
    ("win32", "AMD64", "whisper-bin-x64.zip"),
    ("linux", "x86_64", "whisper-bin-ubuntu-x64.tar.gz"),
])
def test_each_system_gets_its_own_pinned_build(monkeypatch, system, machine, archive):
    monkeypatch.setattr(whisper.sys, "platform", system)
    monkeypatch.setattr(whisper.platform, "machine", lambda: machine)
    assert whisper.build().archive == archive and len(whisper.build().sha256) == 64


def test_a_system_with_no_build_is_told_captions_are_spread_instead(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper.sys, "platform", "darwin")
    monkeypatch.setattr(whisper.platform, "machine", lambda: "arm64")
    with pytest.raises(whisper.NoBuild, match="spread over each frame"):
        whisper.install(tmp_path, say=lambda message: None)
    assert whisper.installed(tmp_path) is False


def test_a_tar_that_would_unpack_outside_its_folder_is_refused(tmp_path, monkeypatch):
    import io
    import tarfile
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        data = b"x"
        member = tarfile.TarInfo("../escaped.txt")
        member.size = len(data)
        bundle.addfile(member, io.BytesIO(data))
    monkeypatch.delattr(whisper.tarfile, "data_filter", raising=False)       # the check done by hand
    with pytest.raises(whisper.WhisperError, match="would land outside"):
        whisper._unpack(archive, tmp_path / "into")
    assert not (tmp_path / "escaped.txt").exists()


def test_a_missing_linux_library_is_named_with_its_package(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper, "installed", lambda workspace: True)
    monkeypatch.setattr(whisper, "_program", lambda workspace: tmp_path / "whisper-cli")
    monkeypatch.setattr(whisper.subprocess, "run", lambda *a, **k: whisper.subprocess.CompletedProcess(
        a[0], 127, stdout="", stderr="whisper-cli: error while loading shared libraries: libgomp.so.1: "
                                     "cannot open shared object file: No such file or directory"))
    with pytest.raises(whisper.WhisperError, match="needs the system library libgomp.*sudo apt install libgomp1"):
        whisper.transcribe(tmp_path, tmp_path / "take.wav")


def test_hearing_before_installing_says_how_to_install(tmp_path):
    with pytest.raises(whisper.WhisperError, match="Run `cm video setup`"):
        whisper.transcribe(tmp_path, tmp_path / "take.wav")
