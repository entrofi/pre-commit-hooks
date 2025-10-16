import types
from pathlib import Path

# Import the script as a module without packaging
SCRIPT_PATH = Path(__file__).parent.parent / "hooks" / "adr_scanner.py"
spec = types.ModuleType("adr_scanner")
spec.__file__ = str(SCRIPT_PATH)
exec(SCRIPT_PATH.read_text(encoding="utf-8"), spec.__dict__)  # nosec

def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def test_first_h1_and_fallback(tmp_path: Path):
    f1 = tmp_path / "docs/adr/a.md"
    write(f1, "# Title A\nBody")
    f2 = tmp_path / "docs/adr/b.md"
    write(f2, "No h1 here\nBut first non-empty line")
    assert spec.title_for(f1) == "Title A"
    assert spec.title_for(f2) == "No h1 here"

def test_grouping_by_subdir(tmp_path: Path):
    src = tmp_path / "docs/adr"
    write(src / "db/001.md", "# DB Choice")
    write(src / "api/002.md", "# API Style")
    write(src / "003.md", "# Root ADR")
    target = tmp_path / "README.md"
    target.write_text("X\n<!--adrlist-->\nOLD\n<!--adrliststop-->\nY", encoding="utf-8")

    files = sorted(spec.iter_markdown_files(src, [], ["md"]), key=lambda p: spec.sort_key("name", p))
    md = spec.build_list_markdown(
        files, target_file=target, src_dir=src,
        group_by="subdir", group_depth=1,
        group_heading_level=2, group_title_case="title"
    )
    # Expect sections: DB, API, Misc
    assert "## Api" in md
    assert "## Db" in md
    assert "## Misc" in md
    assert "- [DB Choice]" in md
    assert "- [API Style]" in md
    assert "- [Root ADR]" in md

def test_replace_between_markers(tmp_path: Path):
    content = "header\n<!--adrlist-->\nOLD\n<!--adrliststop-->\nfooter\n"
    new, changed = spec.replace_between_markers(content, "<!--adrlist-->", "<!--adrliststop-->", "NEW\n")
    assert changed
    assert "NEW" in new
    # running again with same replacement should report no change
    new2, changed2 = spec.replace_between_markers(new, "<!--adrlist-->", "<!--adrliststop-->", "NEW\n")
    assert not changed2

def test_exclude_patterns(tmp_path: Path):
    src = tmp_path / "docs/adr"
    write(src / "keep.md", "# Keep")
    write(src / "archive/old.md", "# Old")
    files = list(spec.iter_markdown_files(src, ["archive/**"], ["md"]))
    names = {f.name for f in files}
    assert "keep.md" in names and "old.md" not in names