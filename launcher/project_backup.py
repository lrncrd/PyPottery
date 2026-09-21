"""
Project backup - export / import of the sub-apps' saved projects.

Lens, Scan and Trace keep each project as a folder under
``<app>/projects/<project_id>/`` (with a ``project.json`` at its root). A backup
is a single zip holding those folders under the same relative layout plus a
``manifest.json``, so it can be restored on any install - including after an
app update or a fresh download of the suite.

Everything here is plain filesystem logic (no Flask) so it can be unit-tested.
"""

import json
import logging
import os
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("launcher.project_backup")

FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
PROJECTS_DIRNAME = "projects"
PROJECT_FILE = "project.json"

ACTION_SKIP = "skip"
ACTION_RENAME = "rename"
ACTION_OVERWRITE = "overwrite"
ACTIONS = (ACTION_SKIP, ACTION_RENAME, ACTION_OVERWRITE)

# Formats that are already compressed: deflating them again only burns CPU.
_STORED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".zip", ".pt", ".pth", ".safetensors"}

# How long an uploaded-but-not-yet-applied backup is kept around.
PENDING_MAX_AGE_SECONDS = 3600

# Characters no project folder name may contain (path separators plus the ones
# Windows forbids), so an id read from a zip can never leave ``projects/``.
_BAD_ID_CHARS = set('/\\:*?"<>|\0')


class BackupError(Exception):
    """A backup could not be created or read; the message is user-facing."""


def _is_safe_id(name: str) -> bool:
    return (
        bool(name)
        and name not in (".", "..")
        and not name.startswith(".")
        and not any(c in _BAD_ID_CHARS or ord(c) < 32 for c in name)
        and name == name.strip()
    )


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def _read_project_meta(project_dir: Path) -> dict:
    try:
        with open(project_dir / PROJECT_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def list_projects(app_paths: Dict[str, Path]) -> List[dict]:
    """
    Every saved project across the given apps, newest first.

    ``app_paths`` maps app id -> that app's install directory. Apps without a
    ``projects/`` folder (or none installed) simply contribute nothing.
    """
    found = []
    for app_id, app_path in app_paths.items():
        root = Path(app_path) / PROJECTS_DIRNAME
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if not entry.is_dir() or not _is_safe_id(entry.name):
                continue
            meta = _read_project_meta(entry)
            if not meta:
                # Half-created or foreign folder: not a project the app can open.
                continue
            found.append({
                "app_id": app_id,
                "project_id": entry.name,
                "name": meta.get("project_name") or entry.name,
                "description": meta.get("description") or "",
                "last_modified": meta.get("last_modified") or "",
                "size": _dir_size(entry),
            })
    found.sort(key=lambda p: p["last_modified"], reverse=True)
    return found


def export_projects(
    app_paths: Dict[str, Path],
    selection: Dict[str, List[str]],
    dest_zip: Path,
    launcher_version: str = "",
    app_versions: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Write the selected projects (``{app_id: [project_id, ...]}``) to ``dest_zip``.
    Returns the manifest that was stored in it.
    """
    app_versions = app_versions or {}
    entries = []
    for app_id, project_ids in selection.items():
        app_path = app_paths.get(app_id)
        if app_path is None:
            raise BackupError(f"Unknown application: {app_id}")
        for project_id in project_ids:
            project_dir = Path(app_path) / PROJECTS_DIRNAME / project_id
            if not _is_safe_id(project_id) or not project_dir.is_dir():
                raise BackupError(f"Project not found: {app_id}/{project_id}")
            meta = _read_project_meta(project_dir)
            entries.append((app_id, project_id, project_dir, meta))

    if not entries:
        raise BackupError("No projects selected.")

    manifest = {
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "launcher_version": launcher_version,
        "projects": [
            {
                "app_id": app_id,
                "project_id": project_id,
                "name": meta.get("project_name") or project_id,
                "app_version": app_versions.get(app_id, ""),
            }
            for app_id, project_id, _dir, meta in entries
        ],
    }

    try:
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
            for app_id, project_id, project_dir, _meta in entries:
                prefix = Path(app_id) / PROJECTS_DIRNAME / project_id
                # Keep empty folders: the apps expect e.g. exports/ to exist.
                archive.write(project_dir, prefix.as_posix() + "/")
                for root, dirs, files in os.walk(project_dir):
                    rel_root = Path(root).relative_to(project_dir)
                    for name in dirs:
                        archive.write(Path(root) / name, (prefix / rel_root / name).as_posix() + "/")
                    for name in files:
                        source = Path(root) / name
                        method = (
                            zipfile.ZIP_STORED
                            if source.suffix.lower() in _STORED_EXTS
                            else zipfile.ZIP_DEFLATED
                        )
                        archive.write(source, (prefix / rel_root / name).as_posix(), compress_type=method)
    except OSError as exc:
        raise BackupError(f"Could not write the backup file: {exc}") from exc
    return manifest


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #

def _split_member(name: str):
    """
    ``"<app>/projects/<id>/rest/of/path"`` -> (app, id, rest-parts). Returns
    None for anything that isn't inside a project folder; raises BackupError
    for names that try to escape (zip-slip) or are otherwise unsafe.
    """
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        raise BackupError(f"The backup contains an unsafe path: {name!r}")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise BackupError(f"The backup contains an unsafe path: {name!r}")
    if len(parts) < 3 or parts[1] != PROJECTS_DIRNAME:
        return None
    app_id, project_id, rest = parts[0], parts[2], parts[3:]
    if not _is_safe_id(app_id) or not _is_safe_id(project_id):
        raise BackupError(f"The backup contains an unsafe path: {name!r}")
    for part in rest:
        if any(c in _BAD_ID_CHARS for c in part):
            raise BackupError(f"The backup contains an unsafe path: {name!r}")
    return app_id, project_id, rest


def _validate_archive(archive: zipfile.ZipFile, known_apps) -> Dict[tuple, List[zipfile.ZipInfo]]:
    """Check the zip and group its members per (app_id, project_id)."""
    try:
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
    except (KeyError, ValueError, UnicodeDecodeError):
        raise BackupError("This file is not a PyPottery backup (manifest.json is missing or unreadable).")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("format_version"), int):
        raise BackupError("This file is not a PyPottery backup (invalid manifest).")
    if manifest["format_version"] > FORMAT_VERSION:
        raise BackupError(
            "This backup was made by a newer version of PyPottery. Update the launcher and try again."
        )

    groups: Dict[tuple, List[zipfile.ZipInfo]] = {}
    with_project_file = set()
    for info in archive.infolist():
        if info.filename == MANIFEST_NAME:
            continue
        mode = info.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            raise BackupError(f"The backup contains a symbolic link: {info.filename!r}")
        located = _split_member(info.filename)
        if located is None:
            continue  # stray file outside any project - ignored, never extracted
        app_id, project_id, rest = located
        if app_id not in known_apps:
            raise BackupError(f"The backup refers to an unknown application: {app_id}")
        groups.setdefault((app_id, project_id), []).append(info)
        if rest == [PROJECT_FILE]:
            with_project_file.add((app_id, project_id))

    # A folder without project.json is not something the apps could open.
    groups = {key: infos for key, infos in groups.items() if key in with_project_file}
    if not groups:
        raise BackupError("The backup does not contain any project.")
    return groups


def inspect_backup(zip_path: Path, app_paths: Dict[str, Path]) -> dict:
    """
    Describe a backup file: which projects it holds and which already exist
    on this install (conflicts). Raises BackupError if it isn't usable.
    """
    try:
        with zipfile.ZipFile(zip_path) as archive:
            bad = archive.testzip()
            if bad:
                raise BackupError(f"The backup is corrupted (damaged file: {bad}).")
            groups = _validate_archive(archive, set(app_paths))
            projects = []
            for (app_id, project_id), infos in groups.items():
                meta = {}
                try:
                    meta = json.loads(
                        archive.read(f"{app_id}/{PROJECTS_DIRNAME}/{project_id}/{PROJECT_FILE}").decode("utf-8")
                    )
                except (KeyError, ValueError, UnicodeDecodeError):
                    pass
                existing = Path(app_paths[app_id]) / PROJECTS_DIRNAME / project_id
                projects.append({
                    "app_id": app_id,
                    "project_id": project_id,
                    "name": (meta.get("project_name") if isinstance(meta, dict) else None) or project_id,
                    "size": sum(i.file_size for i in infos),
                    "exists": existing.exists(),
                })
    except zipfile.BadZipFile:
        raise BackupError("This file is not a valid zip archive.")
    except OSError as exc:
        raise BackupError(f"Could not read the backup file: {exc}") from exc
    projects.sort(key=lambda p: (p["app_id"], p["name"].lower()))
    return {"projects": projects, "total_size": sum(p["size"] for p in projects)}


def _unique_project_id(projects_root: Path, base: str) -> str:
    candidate = f"{base}_imported"
    counter = 2
    while (projects_root / candidate).exists():
        candidate = f"{base}_imported_{counter}"
        counter += 1
    return candidate


def _retarget_project_json(project_dir: Path, project_id: str):
    """The apps look a project up by the id stored in project.json - keep it in
    step with the folder name when an import had to rename the project."""
    meta_path = project_dir / PROJECT_FILE
    meta = _read_project_meta(project_dir)
    if meta.get("project_id") in (None, project_id):
        return
    meta["project_id"] = project_id
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)


def apply_backup(
    zip_path: Path,
    app_paths: Dict[str, Path],
    choices: List[dict],
) -> List[dict]:
    """
    Restore projects from a backup. ``choices`` is a list of
    ``{"app_id", "project_id", "action"}`` with action skip|rename|overwrite
    (only consulted when the project already exists; otherwise it is simply
    restored). Each project is extracted to a staging folder first, so a failure
    never leaves a half-written project behind. Returns one result per choice.
    """
    results = []
    try:
        archive_ctx = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise BackupError(f"Could not read the backup file: {exc}") from exc

    with archive_ctx as archive:
        groups = _validate_archive(archive, set(app_paths))

        for choice in choices:
            app_id = choice.get("app_id")
            project_id = choice.get("project_id")
            action = choice.get("action") or ACTION_RENAME
            result = {"app_id": app_id, "project_id": project_id, "status": "error", "message": ""}
            results.append(result)

            infos = groups.get((app_id, project_id))
            if infos is None or action not in ACTIONS:
                result["message"] = "Not part of this backup."
                continue

            projects_root = Path(app_paths[app_id]) / PROJECTS_DIRNAME
            target = projects_root / project_id
            if target.exists() and action == ACTION_SKIP:
                result.update(status="skipped", message="Already exists - kept the existing one.")
                continue

            need = sum(i.file_size for i in infos)
            try:
                projects_root.mkdir(parents=True, exist_ok=True)
                free = shutil.disk_usage(projects_root).free
                if need > free:
                    result["message"] = "Not enough free disk space."
                    continue
            except OSError as exc:
                result["message"] = str(exc)
                continue

            staging = projects_root / f".import-{uuid.uuid4().hex[:8]}"
            try:
                _extract_project(archive, infos, app_id, project_id, staging)
                final_id = project_id
                if target.exists():
                    if action == ACTION_OVERWRITE:
                        old = projects_root / f".old-{int(time.time())}-{project_id}"
                        target.rename(old)
                        try:
                            staging.rename(target)
                        except OSError:
                            old.rename(target)  # put the original back
                            raise
                        shutil.rmtree(old, ignore_errors=True)
                    else:
                        final_id = _unique_project_id(projects_root, project_id)
                        staging.rename(projects_root / final_id)
                else:
                    staging.rename(target)
                _retarget_project_json(projects_root / final_id, final_id)
                result.update(
                    status="imported" if final_id == project_id else "renamed",
                    project_id=final_id,
                    message="" if final_id == project_id else f"Saved as {final_id}.",
                )
            except (OSError, BackupError) as exc:
                logger.exception("Importing %s/%s failed", app_id, project_id)
                result["message"] = str(exc)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
    return results


def _extract_project(archive, infos, app_id, project_id, staging: Path):
    staging.mkdir(parents=True)
    staging_resolved = staging.resolve()
    for info in infos:
        located = _split_member(info.filename)
        _app, _pid, rest = located
        destination = staging.joinpath(*rest) if rest else staging
        # _split_member already rejects "..", but resolve() is the belt to its braces.
        if staging_resolved not in destination.resolve().parents and destination.resolve() != staging_resolved:
            raise BackupError(f"The backup contains an unsafe path: {info.filename!r}")
        if info.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, open(destination, "wb") as out:
            shutil.copyfileobj(source, out, 1024 * 1024)


# --------------------------------------------------------------------------- #
# Uploaded backups waiting for the user to confirm the import
# --------------------------------------------------------------------------- #

class PendingImports:
    """Uploaded zips kept between the 'inspect' and 'apply' steps."""

    def __init__(self, directory: Optional[Path] = None):
        self._dir = Path(directory) if directory else Path(tempfile.gettempdir()) / "pypottery_backups"
        self._files: Dict[str, Path] = {}

    def new_path(self) -> tuple:
        self._dir.mkdir(parents=True, exist_ok=True)
        self.purge_old()
        token = uuid.uuid4().hex
        path = self._dir / f"{token}.zip"
        self._files[token] = path
        return token, path

    def get(self, token: str) -> Optional[Path]:
        path = self._files.get(token)
        return path if path and path.exists() else None

    def discard(self, token: str):
        path = self._files.pop(token, None)
        if path:
            path.unlink(missing_ok=True)

    def purge_old(self):
        cutoff = time.time() - PENDING_MAX_AGE_SECONDS
        for token, path in list(self._files.items()):
            try:
                stale = not path.exists() or path.stat().st_mtime < cutoff
            except OSError:
                stale = True
            if stale:
                self.discard(token)
        # Also sweep files orphaned by a previous launcher run.
        if self._dir.exists():
            for leftover in self._dir.glob("*.zip"):
                try:
                    if leftover.stem not in self._files and leftover.stat().st_mtime < cutoff:
                        leftover.unlink(missing_ok=True)
                except OSError:
                    pass


def preserve_projects(old_dir: Path, new_dir: Path) -> bool:
    """
    Carry ``old_dir/projects`` over into a freshly installed ``new_dir`` so an
    app update never throws the user's work away. Projects that also exist in
    the new copy (shouldn't happen - a release ships none) win over nothing.
    Returns True if anything was moved.
    """
    source = Path(old_dir) / PROJECTS_DIRNAME
    if not source.is_dir():
        return False
    target = Path(new_dir) / PROJECTS_DIRNAME
    if not target.exists():
        shutil.move(str(source), str(target))
        return True
    moved = False
    for entry in source.iterdir():
        destination = target / entry.name
        if destination.exists():
            continue
        shutil.move(str(entry), str(destination))
        moved = True
    return moved
