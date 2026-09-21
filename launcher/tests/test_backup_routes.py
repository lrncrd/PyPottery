import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from launcher import project_backup as pb
from launcher.web_server import create_app


def _project(app_dir, project_id, name):
    project = app_dir / "projects" / project_id
    (project / "images").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"project_id": project_id, "project_name": name, "last_modified": "2026-01-01"}),
        encoding="utf-8",
    )
    (project / "images" / "a.png").write_bytes(b"png")


@pytest.fixture
def env(tmp_path):
    paths = {a: tmp_path / "apps" / a for a in ("PyPotteryLens", "PyPotteryInk", "PyPotteryScan")}
    for path in paths.values():
        path.mkdir(parents=True)
    _project(paths["PyPotteryLens"], "Prova_1", "Prova")

    running = set()
    manager = SimpleNamespace(
        apps={
            "PyPotteryLens": SimpleNamespace(name="PyPottery Lens", installed=True, installed_version="1.0"),
            "PyPotteryInk": SimpleNamespace(name="PyPottery Ink", installed=True, installed_version="1.0"),
            "PyPotteryScan": SimpleNamespace(name="PyPottery Scan", installed=False, installed_version=None),
        },
        _app_path=lambda app_id: paths[app_id],
        get_app_status=lambda app_id: SimpleNamespace(is_running=app_id in running),
    )
    state = SimpleNamespace(
        app_manager=manager,
        jobs={},
        launcher_version="test",
        pending_imports=pb.PendingImports(tmp_path / "pending"),
        log=lambda *a, **k: None,
    )
    return SimpleNamespace(client=create_app(state).test_client(), paths=paths, running=running)


def _upload(env, payload: bytes):
    return env.client.post(
        "/api/projects/import/inspect",
        data={"file": (io.BytesIO(payload), "backup.zip")},
        content_type="multipart/form-data",
    )


def test_list_export_import_round_trip(env):
    listed = env.client.get("/api/projects").get_json()
    assert [p["project_id"] for p in listed["projects"]] == ["Prova_1"]
    assert listed["projects"][0]["app_name"] == "PyPottery Lens"

    exported = env.client.post("/api/projects/export", json={"selection": {"PyPotteryLens": ["Prova_1"]}})
    assert exported.status_code == 200
    assert "attachment" in exported.headers["Content-Disposition"]
    payload = exported.data
    assert "manifest.json" in zipfile.ZipFile(io.BytesIO(payload)).namelist()
    exported.close()

    inspected = _upload(env, payload).get_json()
    assert inspected["success"] and inspected["projects"][0]["exists"] is True
    choice = {"app_id": "PyPotteryLens", "project_id": "Prova_1", "action": "rename"}

    applied = env.client.post(
        "/api/projects/import/apply", json={"token": inspected["token"], "choices": [choice]}
    ).get_json()
    assert applied["results"][0]["status"] == "renamed"
    assert (env.paths["PyPotteryLens"] / "projects" / "Prova_1_imported" / "images" / "a.png").exists()

    # the token is single-use
    again = env.client.post("/api/projects/import/apply", json={"token": inspected["token"], "choices": [choice]})
    assert again.status_code == 410


def test_export_validation(env):
    assert env.client.post("/api/projects/export", json={"selection": {}}).status_code == 400
    bad = env.client.post("/api/projects/export", json={"selection": {"PyPotteryLens": ["missing"]}})
    assert bad.status_code == 400


def test_import_rejects_garbage(env):
    response = _upload(env, b"not a zip")
    assert response.status_code == 400 and response.get_json()["success"] is False


def test_import_blocked_when_app_running_or_not_installed(env):
    env.running.add("PyPotteryLens")
    exported = env.client.post("/api/projects/export", json={"selection": {"PyPotteryLens": ["Prova_1"]}})
    payload = exported.data
    exported.close()

    inspected = _upload(env, payload).get_json()
    assert "running" in inspected["projects"][0]["busy"]

    result = env.client.post("/api/projects/import/apply", json={
        "token": inspected["token"],
        "choices": [{"app_id": "PyPotteryLens", "project_id": "Prova_1", "action": "overwrite"}],
    }).get_json()
    assert result["results"][0]["status"] == "error"
    assert not (env.paths["PyPotteryLens"] / "projects" / "Prova_1_imported").exists()

    # a backup naming an app that is known but not installed cannot be restored either
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format_version": pb.FORMAT_VERSION}))
        archive.writestr("PyPotteryScan/projects/S/project.json", "{}")
    inspected = _upload(env, buffer.getvalue()).get_json()
    assert inspected["projects"][0]["installed"] is False
    result = env.client.post("/api/projects/import/apply", json={
        "token": inspected["token"],
        "choices": [{"app_id": "PyPotteryScan", "project_id": "S", "action": "rename"}],
    }).get_json()
    assert result["results"][0]["status"] == "error"
    assert not (env.paths["PyPotteryScan"] / "projects").exists()
