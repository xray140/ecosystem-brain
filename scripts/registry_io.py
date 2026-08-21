#!/usr/bin/env python3
"""Read/write the installed-items registry, split shared vs machine-local.

Why the split. `registry/installed.json` is tracked in git, but two of its
fields describe one particular computer: `global_path` (an absolute path under
a username) and `installed_at` (when *this* machine installed the item). With
both in the tracked file, every machine rewrote every entry, so two checkouts
could not pull from each other without a conflict on each line — and a machine
that had merely not bootstrapped yet appeared, in the committed file, to have
agents it did not have.

So:
  registry/installed.json        tracked   — name, source, hash, ref, commit
  registry/installed.local.json  ignored   — global_path, installed_at, per name

Callers see neither. `load()` returns the merged, flat shape the registry has
always had, and `save()` splits it again on the way out, so existing code reads
and writes entries exactly as before.

Legacy files migrate themselves: a tracked entry still carrying the machine
fields is read as this machine's local values, and the next `save()` writes
them to the local file and drops them from the shared one.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry"
SHARED_FILE = REGISTRY_DIR / "installed.json"
LOCAL_FILE = REGISTRY_DIR / "installed.local.json"

KINDS = ("agents", "commands", "skills")

#: Fields that describe this computer rather than the item. Anything listed here
#: is stripped from the tracked file and kept in the gitignored one.
MACHINE_FIELDS = ("global_path", "installed_at")

SHARED_VERSION = 2
LOCAL_VERSION = 1


def _read_json(path: Path, tolerant: bool = False) -> dict:
    """Read a JSON file. `tolerant` treats a corrupt file as empty.

    Set for the machine-local half only: it is gitignored and regenerated on the
    next install, whereas a corrupt tracked file is a real problem that must not
    be papered over. Keyed off the call site rather than comparing against the
    module-level path, so an injected path (tests, a temporary registry) gets
    the same tolerance the real one does.
    """
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        if tolerant:
            return {}
        raise


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def machine_id() -> str:
    return platform.node() or "unknown"


def local_path_for(shared: Path) -> Path:
    """The machine-local sibling of a shared registry file.

    Derived rather than fixed so that a caller pointing at a temporary registry
    (tests, `--dest-root`) gets both halves in the same directory instead of
    silently writing the local half into the real repo.
    """
    return shared.with_name(shared.stem + ".local" + shared.suffix)


def load(shared_file: Path | None = None) -> dict:
    """The merged registry, in the flat shape callers have always used."""
    shared_file = shared_file or SHARED_FILE
    shared = _read_json(shared_file)
    local = _read_json(local_path_for(shared_file), tolerant=True)
    merged: dict = {"_version": SHARED_VERSION}
    for kind in KINDS:
        local_kind = local.get(kind, {}) or {}
        entries = []
        for entry in shared.get(kind, []) or []:
            merged_entry = dict(entry)
            # Legacy machine fields already inline win nothing over the local
            # file; the local file is the newer, authoritative half when both
            # exist, and the inline copy is what we are migrating away from.
            for field, value in (local_kind.get(entry["name"]) or {}).items():
                merged_entry[field] = value
            entries.append(merged_entry)
        merged[kind] = entries
    return merged


def save(merged: dict, shared_file: Path | None = None) -> None:
    """Split a merged registry back into its tracked and machine-local halves."""
    shared_file = shared_file or SHARED_FILE
    shared: dict = {"_version": SHARED_VERSION}
    local: dict = {"_version": LOCAL_VERSION, "machine": machine_id()}
    for kind in KINDS:
        shared_entries = []
        local_entries: dict = {}
        for entry in merged.get(kind, []) or []:
            shared_entry = {k: v for k, v in entry.items() if k not in MACHINE_FIELDS}
            shared_entries.append(shared_entry)
            mine = {k: entry[k] for k in MACHINE_FIELDS if entry.get(k) is not None}
            if mine:
                local_entries[entry["name"]] = mine
        shared[kind] = shared_entries
        local[kind] = local_entries
    _write_json(shared_file, shared)
    _write_json(local_path_for(shared_file), local)


def needs_migration(shared_file: Path | None = None) -> bool:
    """True when the tracked file still carries machine-local fields."""
    shared = _read_json(shared_file or SHARED_FILE)
    return any(
        field in entry
        for kind in KINDS
        for entry in shared.get(kind, []) or []
        for field in MACHINE_FIELDS
    )


def migrate(shared_file: Path | None = None) -> int:
    """Rewrite a legacy registry into the split form. Returns entries moved."""
    shared_file = shared_file or SHARED_FILE
    shared = _read_json(shared_file)
    moved = sum(
        1
        for kind in KINDS
        for entry in shared.get(kind, []) or []
        if any(field in entry for field in MACHINE_FIELDS)
    )
    save(load(shared_file), shared_file)
    return moved


if __name__ == "__main__":
    if needs_migration():
        n = migrate()
        print(f"[ok] migrated {n} entr(ies) -> {SHARED_FILE.name} + {LOCAL_FILE.name}")
    else:
        print("[ok] registry already split — nothing to migrate")
