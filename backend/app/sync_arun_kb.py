"""CLI to sync local ARUN documents into OpenAI File Search."""

from __future__ import annotations

from collections import Counter

from openai import APIError, OpenAIError

from .arun_kb import (
    ArunKBConfig,
    ArunKBConfigError,
    discover_source_files,
    ensure_vector_store,
    file_record_from_manifest,
    get_openai_client,
    load_manifest,
    local_file_record,
    manifest_entry,
    mark_removed_files,
    save_manifest,
    should_upload,
    sync_file,
)


def main() -> int:
    try:
        config = ArunKBConfig.from_env()
        config.ensure_paths()

        manifest = load_manifest(config.manifest_path)
        client = get_openai_client()
        vector_store_id = ensure_vector_store(client, config, manifest)
        manifest["vector_store_id"] = vector_store_id
        manifest.setdefault("files", {})

        source_files = discover_source_files(config.kb_root)
        discovered_paths = {str(path.resolve()) for path in source_files}
        removed_paths = mark_removed_files(discovered_paths, manifest)

        stats = Counter()
        for source_path in source_files:
            local_record = local_file_record(source_path)
            raw_manifest_record = manifest["files"].get(local_record.path)
            manifest_record = (
                file_record_from_manifest(raw_manifest_record)
                if isinstance(raw_manifest_record, dict)
                else None
            )

            if local_record.size == 0:
                print(f"Skipping empty file: {source_path.name}")
                manifest["files"][local_record.path] = {
                    "path": local_record.path,
                    "size": local_record.size,
                    "modified_at_ns": local_record.modified_at_ns,
                    "openai_file_id": "",
                    "vector_store_file_id": "",
                    "vector_store_id": vector_store_id,
                    "status": "skipped_empty",
                }
                save_manifest(config.manifest_path, manifest)
                stats["empty"] += 1
                continue

            if not should_upload(local_record, manifest_record, vector_store_id):
                print(f"Skipping unchanged file: {source_path.name}")
                stats["skipped"] += 1
                continue

            print(f"Syncing file: {source_path.name}")
            synced_record = sync_file(client, vector_store_id, source_path, local_record)
            manifest["files"][local_record.path] = manifest_entry(synced_record)
            save_manifest(config.manifest_path, manifest)
            stats["uploaded"] += 1

        save_manifest(config.manifest_path, manifest)

        print("")
        print(f"Vector store ID: {vector_store_id}")
        print(f"Manifest path: {config.manifest_path}")
        print(f"Uploaded: {stats['uploaded']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Empty skipped: {stats['empty']}")
        if removed_paths:
            print("Removed locally but kept remotely:")
            for removed_path in removed_paths:
                print(f"  - {removed_path}")
        else:
            print("Removed locally but kept remotely: none")

        if config.vector_store_id != vector_store_id:
            print("")
            print("Set OPENAI_VECTOR_STORE_ID to this value before running the backend.")

        return 0
    except ArunKBConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1
    except APIError as exc:
        print(f"OpenAI API error: {exc}")
        return 1
    except OpenAIError as exc:
        print(f"OpenAI client error: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"Sync failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
