from __future__ import annotations

from pathlib import Path

from app.arun_kb import discover_source_files


def test_discover_source_files_includes_supported_top_level_and_nested_sources(
    tmp_path: Path,
) -> None:
    included = [
        tmp_path / "guide.docx",
        tmp_path / "juicing_YT_raw_transcripts" / "day1.txt",
        tmp_path / "juicing_YT_raw_transcripts" / "archive" / "day2.txt",
        tmp_path / "blogs" / "post.txt",
        tmp_path / "books" / "book.pdf",
    ]
    excluded = [
        tmp_path / "notes.txt",
        tmp_path / "books" / "cover.jpg",
        tmp_path / "blogs" / "draft.docx",
    ]

    for path in included + excluded:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sample", encoding="utf-8")

    discovered = discover_source_files(tmp_path)

    assert discovered == [
        tmp_path / "guide.docx",
        tmp_path / "juicing_YT_raw_transcripts" / "archive" / "day2.txt",
        tmp_path / "juicing_YT_raw_transcripts" / "day1.txt",
        tmp_path / "blogs" / "post.txt",
        tmp_path / "books" / "book.pdf",
    ]
