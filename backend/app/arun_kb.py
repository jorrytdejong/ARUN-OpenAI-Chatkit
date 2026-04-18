"""Utilities for syncing the ARUN knowledge base into OpenAI File Search."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_VECTOR_STORE_NAME = "ARUN Knowledge Base"
MANIFEST_VERSION = 1
SUPPORTED_TOP_LEVEL_EXTENSIONS = {".docx"}
SUPPORTED_NESTED_DIRECTORIES = {
    "juicing_YT_raw_transcripts": {".txt"},
    "blogs": {".txt"},
    "books": {".pdf"},
}


class ArunKBConfigError(RuntimeError):
    """Raised when the ARUN knowledge-base configuration is invalid."""


def _workspace_root() -> Path:
    resolved = Path(__file__).resolve()
    if len(resolved.parents) > 5:
        return resolved.parents[5]
    if len(resolved.parents) > 2:
        return resolved.parents[2]
    return resolved.parent


def default_kb_root() -> Path:
    return _workspace_root() / "ARUN data"


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".arun_kb_manifest.json"


@dataclass(slots=True)
class ArunKBConfig:
    kb_root: Path
    manifest_path: Path
    vector_store_id: str | None
    vector_store_name: str

    @classmethod
    def from_env(cls) -> "ArunKBConfig":
        kb_root_env = os.environ.get("ARUN_KB_ROOT")
        manifest_path_env = os.environ.get("ARUN_KB_MANIFEST_PATH")
        return cls(
            kb_root=(
                Path(kb_root_env).expanduser() if kb_root_env else default_kb_root()
            ),
            manifest_path=(
                Path(manifest_path_env).expanduser()
                if manifest_path_env
                else default_manifest_path()
            ),
            vector_store_id=os.environ.get("OPENAI_VECTOR_STORE_ID") or None,
            vector_store_name=os.environ.get(
                "ARUN_KB_VECTOR_STORE_NAME", DEFAULT_VECTOR_STORE_NAME
            ),
        )

    def require_vector_store_id(self) -> str:
        if self.vector_store_id:
            return self.vector_store_id

        manifest = load_manifest(self.manifest_path)
        manifest_vector_store_id = manifest.get("vector_store_id")
        if manifest_vector_store_id:
            self.vector_store_id = manifest_vector_store_id
            return manifest_vector_store_id

        if not self.vector_store_id:
            raise ArunKBConfigError(
                "OPENAI_VECTOR_STORE_ID is required. Run the sync command first or keep "
                f"the manifest at {self.manifest_path} so the backend can recover the "
                "vector store ID automatically."
            )
        return self.vector_store_id

    def ensure_paths(self) -> None:
        if not self.kb_root.exists():
            raise ArunKBConfigError(
                f"ARUN knowledge-base root does not exist: {self.kb_root}"
            )
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class LocalFileRecord:
    path: str
    size: int
    modified_at_ns: int


@dataclass(slots=True)
class ManifestFileRecord:
    path: str
    size: int
    modified_at_ns: int
    openai_file_id: str
    vector_store_file_id: str
    vector_store_id: str
    status: str


def discover_source_files(kb_root: Path) -> list[Path]:
    source_files = [
        path
        for path in sorted(kb_root.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_TOP_LEVEL_EXTENSIONS
    ]

    for directory_name, extensions in SUPPORTED_NESTED_DIRECTORIES.items():
        directory = kb_root / directory_name
        if not directory.exists():
            continue

        source_files.extend(
            path
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path.suffix.lower() in extensions
        )

    return source_files


def local_file_record(path: Path) -> LocalFileRecord:
    stat = path.stat()
    return LocalFileRecord(
        path=str(path.resolve()),
        size=stat.st_size,
        modified_at_ns=stat.st_mtime_ns,
    )


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": MANIFEST_VERSION,
            "vector_store_id": None,
            "files": {},
        }
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ArunKBConfigError(f"Manifest at {path} is not a JSON object.")
    data.setdefault("version", MANIFEST_VERSION)
    data.setdefault("vector_store_id", None)
    data.setdefault("files", {})
    return data


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def ensure_openai_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise ArunKBConfigError(
            "OPENAI_API_KEY is required to sync or query the ARUN knowledge base."
        )


def get_openai_client() -> OpenAI:
    ensure_openai_api_key()
    return OpenAI()


def find_vector_store_by_name(client: OpenAI, name: str) -> str | None:
    for vector_store in client.vector_stores.list(limit=100):
        if vector_store.name == name:
            return vector_store.id
    return None


def ensure_vector_store(client: OpenAI, config: ArunKBConfig, manifest: dict[str, Any]) -> str:
    candidate_id = config.vector_store_id or manifest.get("vector_store_id")
    if candidate_id:
        client.vector_stores.retrieve(candidate_id)
        return candidate_id

    existing_id = find_vector_store_by_name(client, config.vector_store_name)
    if existing_id:
        manifest["vector_store_id"] = existing_id
        return existing_id

    vector_store = client.vector_stores.create(name=config.vector_store_name)
    manifest["vector_store_id"] = vector_store.id
    return vector_store.id


def file_record_from_manifest(data: dict[str, Any]) -> ManifestFileRecord:
    return ManifestFileRecord(
        path=data["path"],
        size=int(data["size"]),
        modified_at_ns=int(data["modified_at_ns"]),
        openai_file_id=data["openai_file_id"],
        vector_store_file_id=data["vector_store_file_id"],
        vector_store_id=data["vector_store_id"],
        status=data["status"],
    )


def should_upload(
    local_record: LocalFileRecord, manifest_record: ManifestFileRecord | None, vector_store_id: str
) -> bool:
    if manifest_record is None:
        return True
    if manifest_record.vector_store_id != vector_store_id:
        return True
    if manifest_record.status != "completed":
        return True
    return (
        manifest_record.size != local_record.size
        or manifest_record.modified_at_ns != local_record.modified_at_ns
    )


def sync_file(
    client: OpenAI, vector_store_id: str, source_path: Path, local_record: LocalFileRecord
) -> ManifestFileRecord:
    with source_path.open("rb") as handle:
        openai_file = client.files.create(file=handle, purpose="assistants")

    vector_store_file = client.vector_stores.files.create_and_poll(
        vector_store_id=vector_store_id,
        file_id=openai_file.id,
        attributes={"source_path": local_record.path},
        poll_interval_ms=1_000,
    )
    if vector_store_file.status != "completed":
        raise RuntimeError(
            f"Indexing failed for {source_path.name}: "
            f"vector store file status is {vector_store_file.status}"
        )

    return ManifestFileRecord(
        path=local_record.path,
        size=local_record.size,
        modified_at_ns=local_record.modified_at_ns,
        openai_file_id=openai_file.id,
        vector_store_file_id=vector_store_file.id,
        vector_store_id=vector_store_id,
        status=vector_store_file.status,
    )


def mark_removed_files(
    discovered_paths: set[str], manifest: dict[str, Any]
) -> list[str]:
    removed = []
    for path in sorted(manifest.get("files", {})):
        if path not in discovered_paths:
            removed.append(path)
    return removed


def manifest_entry(record: ManifestFileRecord) -> dict[str, Any]:
    return asdict(record)
