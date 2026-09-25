"""The video toolchain: setup checks each step, and the starter's packages stay pinned."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cm import toolchain

STARTER = Path(__file__).resolve().parent.parent / "cm" / "starter" / "video"


class FakeRun:
    """Stands in for subprocess.run: records each command, fails the one it is told to."""

    def __init__(self, node: str = "v24.1.0", fail: str | None = None) -> None:
        self.node, self.fail, self.calls = node, fail, []

    def __call__(self, argv, cwd=None, **kwargs):
        self.calls.append((argv[1:], cwd))
        failed = self.fail is not None and self.fail in argv
        return subprocess.CompletedProcess(argv, 1 if failed else 0, stdout=self.node + "\n")


@pytest.fixture
def workspace(tmp_path):
    for name in toolchain.MANIFESTS:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: f"/bin/{name}")


def _setup(monkeypatch, workspace, run: FakeRun) -> list[str]:
    monkeypatch.setattr(toolchain.subprocess, "run", run)
    said: list[str] = []
    toolchain.setup(workspace, say=said.append)
    return said


def test_setup_installs_from_the_lockfile_checks_signatures_then_fetches_the_browser(monkeypatch, workspace, tools):
    run = FakeRun()
    said = _setup(monkeypatch, workspace, run)

    assert run.calls == [
        (["--version"], None),
        (["ci", "--ignore-scripts", "--no-audit", "--no-fund"], workspace),
        (["audit", "signatures"], workspace),
        (["exec", "--no", "--", "remotion", "browser", "ensure"], workspace),
    ]
    assert said[0] == "Node 24.1.0 found." and said[-1] == "The video toolchain is ready."


def test_a_failed_signature_check_stops_before_the_browser_is_fetched(monkeypatch, workspace, tools):
    run = FakeRun(fail="signatures")
    with pytest.raises(toolchain.ToolchainError, match="may have been tampered with"):
        _setup(monkeypatch, workspace, run)
    assert not any("browser" in argv for argv, _ in run.calls)


def test_a_failed_install_stops_everything_after_it(monkeypatch, workspace, tools):
    run = FakeRun(fail="ci")
    with pytest.raises(toolchain.ToolchainError, match="Installing the packages failed"):
        _setup(monkeypatch, workspace, run)
    assert len(run.calls) == 2


def test_setup_needs_cm_init_first(monkeypatch, tmp_path, tools):
    with pytest.raises(toolchain.ToolchainError, match="Run `cm init` first"):
        _setup(monkeypatch, tmp_path, FakeRun())


def test_setup_says_how_to_get_node(monkeypatch, workspace):
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: None)
    with pytest.raises(toolchain.ToolchainError, match="node is not on PATH. Install Node 18"):
        _setup(monkeypatch, workspace, FakeRun())


def test_an_old_node_is_refused(monkeypatch, workspace, tools):
    with pytest.raises(toolchain.ToolchainError, match="v16.20.0 is too old"):
        _setup(monkeypatch, workspace, FakeRun(node="v16.20.0"))


# --- what the starter pins ------------------------------------------------------------------

def _manifests() -> tuple[dict, dict]:
    package = json.loads((STARTER / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((STARTER / "package-lock.json").read_text(encoding="utf-8"))
    return package, lock


def test_every_package_is_pinned_to_one_exact_version():
    package, lock = _manifests()
    for name, version in package["dependencies"].items():
        assert version[0].isdigit(), f"{name} is not pinned to an exact version: {version}"
    assert lock["packages"][""]["dependencies"] == package["dependencies"], "lockfile is out of date"


def test_every_locked_package_comes_from_the_registry_with_a_checksum():
    _, lock = _manifests()
    for path, entry in lock["packages"].items():
        if path:
            assert entry["resolved"].startswith("https://registry.npmjs.org/"), path
            assert entry["integrity"].startswith("sha512-"), path


def test_no_package_may_run_code_while_installing():
    assert "ignore-scripts=true" in (STARTER / ".npmrc").read_text(encoding="utf-8").splitlines()
