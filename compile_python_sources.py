from __future__ import annotations

import os
import py_compile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ROOT_PYTHON_FILES = (
    PROJECT_ROOT / "app.py",
    PROJECT_ROOT / "compile_python_sources.py",
    PROJECT_ROOT / "listcompare_launcher.py",
)
SCAN_ROOTS = (
    PROJECT_ROOT / "listcompare",
    PROJECT_ROOT / "tests",
)
SKIP_DIR_NAMES = {
    ".git",
    ".tmp_tests",
    "__pycache__",
    "build",
    "dist",
}


def should_skip_dirname(dirname: str) -> bool:
    return (
        dirname in SKIP_DIR_NAMES
        or dirname.startswith("tmp")
        or dirname.startswith("_tmp_")
    )


def iter_python_files() -> list[Path]:
    paths = [path for path in ROOT_PYTHON_FILES if path.exists()]

    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for current_root, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = sorted(
                dirname for dirname in dirnames if not should_skip_dirname(dirname)
            )
            for filename in sorted(filenames):
                if filename.endswith(".py"):
                    paths.append(Path(current_root) / filename)

    return sorted(dict.fromkeys(path.resolve() for path in paths))


def compile_python_files(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{path}: {exc.msg}")
        except Exception as exc:  # pragma: no cover - defensive formatting
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
    return errors


def main() -> int:
    paths = iter_python_files()
    errors = compile_python_files(paths)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Compiled {len(paths)} Python files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
