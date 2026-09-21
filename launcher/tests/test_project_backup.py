import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher import project_backup as pb
from launcher.app_manager import AppManager


def make_project(app_dir: Path, project_id: str, name: str = "Demo", files=None):
    project = app_dir / "projects" / project_id
    (project / "exports").mkdir(parents=True)  # empty dir must survive a round trip
    (project / "images").mkdir()
    (project / "project.json").write_text(
        json.dumps({"project_id": project_id, "project_name": name, "last_modified": "2026-01-01"}),
        encoding="utf-8",
    )
    for rel, data in (files or {"images/a.png": b"\x89PNG-data"}).items():
        (project / rel).write_bytes(data)
    return project


@pytest.fixture
def apps(tmp_path):
    lens, scan = tmp_path / "apps" / "PyPotteryLens", tmp_path / "apps" / "PyPotteryScan"
    lens.mkdir(parents=True)
    scan.mkdir(parents=True)
    return {"PyPotteryLens": lens, "PyPotteryScan": scan}


def test_list_projects(apps):
    make_project(apps["PyPotteryLens"], "Prova_1", "Prova")
    (apps["PyPotteryLens"] / "projects" / ".import-half").mkdir()  # foreign / staging folder
    listed = pb.list_projects(apps)
    assert [(p["app_id"], p["project_id"], p["name"]) for p in listed] == [("PyPotteryLens", "Prova_1", "Prova")]
    assert listed[0]["size"] > 0


def test_round_trip_into_empty_install(apps, tmp_path):
    src = make_project(apps["PyPotteryLens"], "Prova_1", files={"images/a.png": b"abc", "notes.txt": b"hi"})
    make_project(apps["PyPotteryScan"], "Bcc_1")
    backup = tmp_path / "b.zip"
    manifest = pb.export_projects(
        apps, {"PyPotteryLens": ["Prova_1"], "PyPotteryScan": ["Bcc_1"]}, backup, launcher_version="1.1.0"
    )
    assert manifest["format_version"] == pb.FORMAT_VERSION and len(manifest["projects"]) == 2

    # restore into a different install
    other = {a: tmp_path / "other" / a for a in apps}
    for path in other.values():
        path.mkdir(parents=True)
    info = pb.inspect_backup(backup, other)
    assert {p["project_id"] for p in info["projects"]} == {"Prova_1", "Bcc_1"}
    assert not any(p["exists"] for p in info["projects"])

    results = pb.apply_backup(backup, other, [
        {"app_id": p["app_id"], "project_id": p["project_id"], "action": "rename"} for p in info["projects"]
    ])
    assert {r["status"] for r in results} == {"imported"}
    restored = other["PyPotteryLens"] / "projects" / "Prova_1"
    assert (restored / "images" / "a.png").read_bytes() == b"abc"
    assert (restored / "notes.txt").read_bytes() == b"hi"
    assert (restored / "exports").is_dir()
    assert not any(p.name.startswith(".import-") for p in (other["PyPotteryLens"] / "projects").iterdir())
    assert src.exists()  # export never touches the original


def test_conflict_actions(apps, tmp_path):
    make_project(apps["PyPotteryLens"], "Prova_1", "Original", files={"images/a.png": b"old"})
    backup = tmp_path / "b.zip"
    pb.export_projects(apps, {"PyPotteryLens": ["Prova_1"]}, backup)
    # change the live copy so we can tell which one wins
    (apps["PyPotteryLens"] / "projects" / "Prova_1" / "images" / "a.png").write_bytes(b"live")
    choice = {"app_id": "PyPotteryLens", "project_id": "Prova_1"}

    assert pb.inspect_backup(backup, apps)["projects"][0]["exists"] is True

    assert pb.apply_backup(backup, apps, [{**choice, "action": "skip"}])[0]["status"] == "skipped"
    assert (apps["PyPotteryLens"] / "projects" / "Prova_1" / "images" / "a.png").read_bytes() == b"live"

    renamed = pb.apply_backup(backup, apps, [{**choice, "action": "rename"}])[0]
    assert renamed["status"] == "renamed" and renamed["project_id"] == "Prova_1_imported"
    copy = apps["PyPotteryLens"] / "projects" / "Prova_1_imported"
    assert (copy / "images" / "a.png").read_bytes() == b"old"
    # the apps look projects up by the id inside project.json
    assert json.loads((copy / "project.json").read_text())["project_id"] == "Prova_1_imported"

    assert pb.apply_backup(backup, apps, [{**choice, "action": "overwrite"}])[0]["status"] == "imported"
    assert (apps["PyPotteryLens"] / "projects" / "Prova_1" / "images" / "a.png").read_bytes() == b"old"
    assert not [p for p in (apps["PyPotteryLens"] / "projects").iterdir() if p.name.startswith(".")]


def _zip(path: Path, members: dict):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


MANIFEST = json.dumps({"format_version": pb.FORMAT_VERSION})


@pytest.mark.parametrize("evil", [
    "PyPotteryLens/projects/P/../../../evil.txt",
    "PyPotteryLens/projects/../../evil.txt",
    "/abs/evil.txt",
    "C:/evil.txt",
    "PyPotteryLens/projects/..\\..\\evil.txt",
])
def test_zip_slip_rejected(apps, tmp_path, evil):
    backup = _zip(tmp_path / "evil.zip", {
        "manifest.json": MANIFEST,
        "PyPotteryLens/projects/P/project.json": "{}",
        evil: "x",
    })
    with pytest.raises(pb.BackupError):
        pb.inspect_backup(backup, apps)
    with pytest.raises(pb.BackupError):
        pb.apply_backup(backup, apps, [{"app_id": "PyPotteryLens", "project_id": "P", "action": "rename"}])
    assert not (tmp_path / "evil.txt").exists()


def test_invalid_backups(apps, tmp_path):
    not_zip = tmp_path / "x.zip"
    not_zip.write_text("nope")
    with pytest.raises(pb.BackupError):
        pb.inspect_backup(not_zip, apps)

    no_manifest = _zip(tmp_path / "m.zip", {"PyPotteryLens/projects/P/project.json": "{}"})
    with pytest.raises(pb.BackupError, match="manifest"):
        pb.inspect_backup(no_manifest, apps)

    newer = _zip(tmp_path / "n.zip", {"manifest.json": json.dumps({"format_version": 99})})
    with pytest.raises(pb.BackupError, match="newer"):
        pb.inspect_backup(newer, apps)

    unknown_app = _zip(tmp_path / "u.zip", {"manifest.json": MANIFEST, "Nope/projects/P/project.json": "{}"})
    with pytest.raises(pb.BackupError, match="unknown application"):
        pb.inspect_backup(unknown_app, apps)

    empty = _zip(tmp_path / "e.zip", {"manifest.json": MANIFEST, "PyPotteryLens/projects/P/other.txt": "x"})
    with pytest.raises(pb.BackupError, match="any project"):
        pb.inspect_backup(empty, apps)


def test_export_rejects_bad_selection(apps, tmp_path):
    with pytest.raises(pb.BackupError):
        pb.export_projects(apps, {}, tmp_path / "b.zip")
    with pytest.raises(pb.BackupError):
        pb.export_projects(apps, {"PyPotteryLens": ["../x"]}, tmp_path / "b.zip")
    with pytest.raises(pb.BackupError):
        pb.export_projects(apps, {"Nope": ["a"]}, tmp_path / "b.zip")


def test_pending_imports(tmp_path):
    pending = pb.PendingImports(tmp_path / "p")
    token, path = pending.new_path()
    assert pending.get(token) is None  # nothing uploaded yet
    path.write_bytes(b"x")
    assert pending.get(token) == path
    pending.discard(token)
    assert pending.get(token) is None and not path.exists()


def test_preserve_projects(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    make_project(old, "P1")
    new.mkdir()
    assert pb.preserve_projects(old, new) is True
    assert (new / "projects" / "P1" / "project.json").exists()
    assert pb.preserve_projects(tmp_path / "missing", new) is False


def test_swap_into_place_keeps_projects(tmp_path):
    apps_dir = tmp_path / "apps"
    app_path = apps_dir / "PyPotteryLens"
    make_project(app_path, "Mine")
    (app_path / "app.py").write_text("old")
    staged = apps_dir / ".staging" / "PyPotteryLens"
    staged.mkdir(parents=True)
    (staged / "app.py").write_text("new")

    fake_self = SimpleNamespace(_rename_with_retry=AppManager._rename_with_retry)
    AppManager._swap_into_place(fake_self, "PyPotteryLens", staged, app_path)

    assert (app_path / "app.py").read_text() == "new"
    assert (app_path / "projects" / "Mine" / "project.json").exists()
    assert not list(apps_dir.glob("*.old-*"))
