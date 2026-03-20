import json
import os
import subprocess
import unittest
from pathlib import Path

from tests._support import cleanup_temp_path, make_temp_dir


REPO_ROOT = Path(__file__).resolve().parents[1]
UPDATER_SCRIPT_PATH = REPO_ROOT / "ListCompare Updater.ps1"
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
class ListCompareUpdaterScriptTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        return make_temp_dir("updater")

    def _run_powershell(self, command: str, *, local_appdata: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(local_appdata)
        env["LISTCOMPARE_UPDATER_SKIP_MAIN"] = "1"
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

    def test_invalid_shared_sync_config_becomes_warning_not_exception(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            config_dir = local_appdata / "ListCompare"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "shared_sync_config.json").write_text("{ invalid json", encoding="utf-8")

            command = rf"""
$ErrorActionPreference = 'Stop'
. '{_ps_literal(UPDATER_SCRIPT_PATH)}'
function Get-ReleaseRootCandidates {{ @() }}
$script:ReleaseRootResolutionWarning = ''
$result = Resolve-ReleaseRootPath -RequestedReleaseRoot ''
[pscustomobject]@{{
    root = $result
    warning = $script:ReleaseRootResolutionWarning
}} | ConvertTo-Json -Compress
"""
            result = self._run_powershell(command, local_appdata=local_appdata)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["root"], "")
        self.assertIn("Could not read shared release config", payload["warning"])

    def test_multiple_candidates_can_fall_back_when_installed_runtime_exists(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            candidate_a = temp_root / "candidate-a"
            candidate_b = temp_root / "candidate-b"
            candidate_a.mkdir(parents=True, exist_ok=True)
            candidate_b.mkdir(parents=True, exist_ok=True)
            (candidate_a / "latest.json").write_text('{"version":"1.0.0","zip":"a.zip"}', encoding="utf-8")
            (candidate_b / "latest.json").write_text('{"version":"1.0.0","zip":"b.zip"}', encoding="utf-8")

            command = rf"""
$ErrorActionPreference = 'Stop'
. '{_ps_literal(UPDATER_SCRIPT_PATH)}'
function Get-ConfiguredSharedReleaseRoot {{ return '' }}
function Get-ReleaseRootCandidates {{ @('{_ps_literal(candidate_a)}', '{_ps_literal(candidate_b)}') }}
$script:ReleaseRootResolutionWarning = ''
$result = Resolve-ReleaseRootPath -RequestedReleaseRoot '' -AllowInstalledFallback
[pscustomobject]@{{
    root = $result
    warning = $script:ReleaseRootResolutionWarning
}} | ConvertTo-Json -Compress
"""
            result = self._run_powershell(command, local_appdata=local_appdata)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["root"], "")
        self.assertIn("Multiple release folders were found", payload["warning"])

    def test_multiple_candidates_still_error_without_fallback(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            candidate_a = temp_root / "candidate-a"
            candidate_b = temp_root / "candidate-b"
            candidate_a.mkdir(parents=True, exist_ok=True)
            candidate_b.mkdir(parents=True, exist_ok=True)
            (candidate_a / "latest.json").write_text('{"version":"1.0.0","zip":"a.zip"}', encoding="utf-8")
            (candidate_b / "latest.json").write_text('{"version":"1.0.0","zip":"b.zip"}', encoding="utf-8")

            command = rf"""
$ErrorActionPreference = 'Stop'
. '{_ps_literal(UPDATER_SCRIPT_PATH)}'
function Get-ConfiguredSharedReleaseRoot {{ return '' }}
function Get-ReleaseRootCandidates {{ @('{_ps_literal(candidate_a)}', '{_ps_literal(candidate_b)}') }}
Resolve-ReleaseRootPath -RequestedReleaseRoot ''
"""
            result = self._run_powershell(command, local_appdata=local_appdata)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Multiple release folders were found", result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
