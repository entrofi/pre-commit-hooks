#!/usr/bin/env python3
import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

H1_REGEX = re.compile(r"^[ \t]*#[ \t]+(.+?)\s*$", re.MULTILINE)

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a markdown list of links from the first H1 of each file.",
    )
    p.add_argument("--src-dir", default="docs/adr",
                   help="Directory to scan for markdown files (recursive).")
    p.add_argument("--target-file", default="README.md",
                   help="File whose content will be updated between markers.")
    p.add_argument("--marker-start", default="<!--adrlist-->",
                   help="Start marker to locate the insertion area.")
    p.add_argument("--marker-end", default="<!--adrliststop-->",
                   help="End marker to locate the insertion area.")
    p.add_argument("--exclude", action="append", default=[],
                   help="Glob patterns to exclude (relative to src-dir). Repeat for multiple.")
    p.add_argument("--extensions", default="md,MD",
                   help="Comma-separated file extensions to include.")
    p.add_argument("--sort", choices=["name", "path", "mtime"], default="name",
                   help="Sort order for entries.")
    p.add_argument("--no-fail-on-change", action="store_true",
                   help="Exit 0 even if target file was modified.")
    # Grouping options
    p.add_argument("--group-by", choices=["none", "subdir"], default="none",
                   help="How to group entries. 'subdir' groups by subfolder(s) under --src-dir.")
    p.add_argument("--group-depth", type=int, default=1,
                   help="Number of path segments under --src-dir that form the group key (when --group-by=subdir).")
    p.add_argument("--group-heading-level", type=int, default=2,
                   help="Markdown heading level for group headers (e.g., 2 => '##').")
    p.add_argument("--group-title-case", choices=["none", "title", "upper", "lower"], default="title",
                   help="Transform applied to group titles.")
    return p.parse_args(argv)

def iter_markdown_files(src_dir: Path, ex_patterns: List[str], exts: List[str]) -> Iterable[Path]:
    rel_ex_patterns = [normalize_glob(p) for p in ex_patterns]
    for p in src_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lstrip(".") not in exts:
            continue
        rel = p.relative_to(src_dir).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in rel_ex_patterns):
            continue
        yield p

def normalize_glob(pat: str) -> str:
    return pat.replace("\\", "/").lstrip("./")

def first_h1(text: str) -> str | None:
    m = H1_REGEX.search(text)
    return m.group(1).strip() if m else None

def title_for(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return path.stem
    h = first_h1(text)
    if h:
        return h
    for line in text.splitlines():
        t = line.strip()
        if t:
            return t
    return path.stem

def sort_key(sort: str, path: Path) -> Tuple:
    if sort == "mtime":
        try:
            return path.stat().st_mtime, path.name.lower()
        except FileNotFoundError:
            return 0, path.name.lower()
    if sort == "path":
        return (path.as_posix().lower(),)
    return (path.name.lower(),)

def apply_case(s: str, mode: str) -> str:
    match mode:
        case "title": return s.replace("-", " ").replace("_", " ").title()
        case "upper": return s.upper()
        case "lower": return s.lower()
        case _:       return s

def group_key_for(path: Path, src_dir: Path, depth: int) -> str:
    rel_parts = path.relative_to(src_dir).parts
    # drop filename
    dirs = list(rel_parts[:-1])
    if not dirs:
        return ""  # files directly under src_dir
    key_parts = dirs[:depth]
    return "/".join(key_parts)

def build_list_markdown(files: List[Path],
                        target_file: Path,
                        src_dir: Path,
                        group_by: str,
                        group_depth: int,
                        group_heading_level: int,
                        group_title_case: str) -> str:
    target_dir = target_file.parent
    def list_item(f: Path) -> str:
        link_title = title_for(f)
        rel_link = os.path.relpath(f.as_posix(), start=target_dir.as_posix())
        safe_title = link_title.replace("[", "\\[").replace("]", "\\]")
        return f"- [{safe_title}]({rel_link})"

    if group_by == "none":
        lines = [list_item(f) for f in files]
        return "\n".join(lines) + ("\n" if lines else "")
    # group_by == "subdir"
    groups: Dict[str, List[Path]] = {}
    for f in files:
        key = group_key_for(f, src_dir, group_depth)
        groups.setdefault(key, []).append(f)

    # stable ordering by group name
    out: List[str] = []
    for key in sorted(groups.keys(), key=lambda k: k.lower()):
        title = key if key else "Misc"
        title = apply_case(title, group_title_case)
        header = "#" * max(1, group_heading_level) + f" {title}"
        out.append(header)
        out.extend(list_item(f) for f in groups[key])
        out.append("")  # blank line after each group
    return "\n".join(out).rstrip() + ("\n" if out else "")

def replace_between_markers(content: str, start: str, end: str, replacement: str) -> Tuple[str, bool]:
    pattern = re.compile(rf"({re.escape(start)})(.*?){re.escape(end)}", flags=re.DOTALL)
    m = pattern.search(content)
    if not m:
        raise RuntimeError(
            f"Markers not found. Ensure both markers exist in target file:\n{start}\n{end}"
        )
    before = content[:m.start(1)]
    after = content[m.end():]
    new = before + start + "\n" + replacement + end + after
    return new, new != content

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    repo_root = Path.cwd()
    src_dir = (repo_root / args.src_dir).resolve()
    target_file = (repo_root / args.target_file).resolve()

    if not src_dir.exists():
        print(f"✖ Source directory not found: {src_dir}", file=sys.stderr)
        return 2
    if not target_file.exists():
        print(f"✖ Target file not found: {target_file}", file=sys.stderr)
        return 2

    exts = [e.strip() for e in args.extensions.split(",") if e.strip()]
    files = sorted(iter_markdown_files(src_dir, args.exclude, exts),
                   key=lambda p: sort_key(args.sort, p))

    list_md = build_list_markdown(
        files, target_file=target_file, src_dir=src_dir,
        group_by=args.group_by, group_depth=args.group_depth,
        group_heading_level=args.group_heading_level,
        group_title_case=args.group_title_case,
    )

    original = target_file.read_text(encoding="utf-8", errors="replace")
    try:
        updated, changed = replace_between_markers(
            original, args.marker_start, args.marker_end, list_md
        )
    except RuntimeError as e:
        print(f"✖ {e}", file=sys.stderr)
        return 3

    if changed:
        target_file.write_text(updated, encoding="utf-8")
        print(f"↻ Updated {target_file} between markers {args.marker_start} … {args.marker_end}")
        return 0 if args.no_fail_on_change else 1

    print("✔ No changes needed")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))