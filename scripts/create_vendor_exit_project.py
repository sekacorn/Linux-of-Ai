"""Create a deterministic Linux of AI vendor-exit quickstart workspace."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPOSITORY_ROOT / "quickstart" / "vendor-exit-template"
PROJECT_NAME_PLACEHOLDER = "{{PROJECT_NAME}}"


class QuickstartError(RuntimeError):
    """Raised when a quickstart workspace cannot be created safely."""


def _is_link_like(path: Path) -> bool:
    """Return whether *path* can redirect writes to another location."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _reject_redirected_destinations(template: Path, target: Path) -> None:
    """Reject template-owned destination paths that traverse links or junctions."""
    checked: set[Path] = set()
    for source in template.rglob("*"):
        current = target
        for part in source.relative_to(template).parts:
            current /= part
            if current in checked:
                continue
            checked.add(current)
            if _is_link_like(current):
                relative_path = current.relative_to(target).as_posix()
                raise QuickstartError(
                    "Refusing to overwrite a symbolic link or junction in the "
                    f"output directory: {relative_path}"
                )


def _display_name(value: str) -> str:
    """Remove terminal control characters from a user-provided path name."""
    cleaned = "".join(
        character if character.isprintable() else " " for character in value
    )
    return " ".join(cleaned.split()) or "linux-ai-quickstart"


def _markdown_name(value: str) -> str:
    """Escape a short project name before placing it in generated Markdown."""
    escaped = _display_name(value).replace("\\", "\\\\")
    for character in "`*_{}[]<>()#+-.!|":
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def create_project(target_argument: Path, *, force: bool = False) -> Path:
    """Copy the bundled template into *target_argument* and return its path."""
    template = TEMPLATE_ROOT.resolve()
    if not template.is_dir():
        raise QuickstartError(f"Quickstart template is missing: {TEMPLATE_ROOT}")

    if _is_link_like(target_argument):
        raise QuickstartError(
            "Refusing to write through a symbolic-link or junction target directory."
        )

    target = target_argument.expanduser().resolve(strict=False)
    if target == template or template in target.parents:
        raise QuickstartError(
            "Output directory cannot be the quickstart template or one of its children."
        )
    if target.exists() and not target.is_dir():
        raise QuickstartError(
            f"Output path exists and is not a directory: {target_argument}"
        )

    target_is_nonempty = target.is_dir() and any(target.iterdir())
    if target_is_nonempty and not force:
        raise QuickstartError(
            f"Output directory is not empty: {target_argument}. Use --force to replace template-owned files."
        )

    target.mkdir(parents=True, exist_ok=True)
    _reject_redirected_destinations(template, target)
    shutil.copytree(
        template,
        target,
        dirs_exist_ok=True,
        copy_function=shutil.copy2,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    readme_path = target / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(
        readme.replace(PROJECT_NAME_PLACEHOLDER, _markdown_name(target.name)),
        encoding="utf-8",
        newline="\n",
    )

    run_script = target / "run.sh"
    if run_script.exists():
        mode = run_script.stat().st_mode
        run_script.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic, offline Linux of AI vendor-exit workspace."
    )
    parser.add_argument(
        "output_directory", type=Path, help="Directory to create or populate."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace template-owned files in a non-empty directory without deleting unrelated files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = create_project(args.output_directory, force=args.force)
    except (OSError, QuickstartError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    project_name = _display_name(target.name)
    relative_target = os.path.relpath(target, Path.cwd())
    print(f"Created Linux of AI quickstart project: {project_name}")
    print()
    print("Next:")
    print(f"  cd {relative_target}")
    print("  python run.py")
    print()
    print("or:")
    print("  make run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
