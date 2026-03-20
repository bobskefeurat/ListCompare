import os
import subprocess
import unittest
from pathlib import Path

from tests._support import cleanup_temp_path, make_temp_dir


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_COMMON_SCRIPT_PATH = REPO_ROOT / "build_common.ps1"
POWERSHELL_EXE = (
    Path(os.environ.get("SystemRoot", r"C:\Windows"))
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)


def _ps_literal(path: Path) -> str:
    return str(path).replace("'", "''")


@unittest.skipUnless(os.name == "nt" and POWERSHELL_EXE.exists(), "Windows PowerShell required")
class BuildScriptTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        return make_temp_dir("build-scripts")

    def _run_powershell(self, command: str, *, local_appdata: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(local_appdata)
        return subprocess.run(
            [
                str(POWERSHELL_EXE),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_resolve_python_exe_prefers_highest_semantic_version(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            python_root = local_appdata / "Python"
            for folder_name in ("pythoncore-3.9-64", "pythoncore-3.14-64", "pythoncore-3.10-64"):
                install_dir = python_root / folder_name
                install_dir.mkdir(parents=True, exist_ok=True)
                (install_dir / "python.exe").write_text("", encoding="utf-8")

            command = rf"""
$ErrorActionPreference = 'Stop'
. '{_ps_literal(BUILD_COMMON_SCRIPT_PATH)}'
Resolve-PythonExe -RequestedPythonExe ''
"""
            result = self._run_powershell(command, local_appdata=local_appdata)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(
            result.stdout.strip(),
            str((python_root / "pythoncore-3.14-64" / "python.exe").resolve()),
        )

    def test_resolve_python_exe_honors_explicit_path(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            requested_python = temp_root / "custom-python" / "python.exe"
            requested_python.parent.mkdir(parents=True, exist_ok=True)
            requested_python.write_text("", encoding="utf-8")

            command = rf"""
$ErrorActionPreference = 'Stop'
. '{_ps_literal(BUILD_COMMON_SCRIPT_PATH)}'
Resolve-PythonExe -RequestedPythonExe '{_ps_literal(requested_python)}'
"""
            result = self._run_powershell(command, local_appdata=local_appdata)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), str(requested_python.resolve()))


if __name__ == "__main__":
    unittest.main()
