import json
import os
import subprocess
import unittest
from pathlib import Path

from tests._support import cleanup_temp_path, make_temp_dir


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT_PATH = REPO_ROOT / "Publish-SharedRelease.ps1"
POWERSHELL_EXE = (
    Path(os.environ.get("SystemRoot", r"C:\Windows"))
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)


@unittest.skipUnless(os.name == "nt" and POWERSHELL_EXE.exists(), "Windows PowerShell required")
class PublishSharedReleaseScriptTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        return make_temp_dir("publish-release")

    def _run_publish_script(
        self,
        *,
        version: str,
        zip_path: Path,
        local_appdata: Path,
        release_root: Path | None = None,
        env_release_root: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(local_appdata)
        if env_release_root is None:
            env.pop("LISTCOMPARE_RELEASE_DIR", None)
        else:
            env["LISTCOMPARE_RELEASE_DIR"] = str(env_release_root)

        command = [
            str(POWERSHELL_EXE),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PUBLISH_SCRIPT_PATH),
            "-Version",
            version,
            "-ZipPath",
            str(zip_path),
        ]
        if release_root is not None:
            command.extend(["-ReleaseRoot", str(release_root)])

        return subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_publish_script_copies_archive_and_writes_manifest(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            release_root = temp_root / "release-root"
            zip_path = temp_root / "artifacts" / "ListCompare-windows.zip"
            release_root.mkdir(parents=True, exist_ok=True)
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            zip_path.write_text("zip payload", encoding="utf-8")

            result = self._run_publish_script(
                version="1.2.3",
                zip_path=zip_path,
                local_appdata=local_appdata,
                release_root=release_root,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            target_archive_path = release_root / "ListCompare-windows-1.2.3.zip"
            latest_manifest_path = release_root / "latest.json"
            self.assertTrue(target_archive_path.exists())
            self.assertEqual(target_archive_path.read_text(encoding="utf-8"), "zip payload")

            manifest = json.loads(latest_manifest_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["version"], "1.2.3")
            self.assertEqual(manifest["zip"], "ListCompare-windows-1.2.3.zip")
            self.assertIn("published_at", manifest)
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)

    def test_publish_script_uses_env_release_root_when_local_sync_config_is_invalid(self) -> None:
        temp_root = self._temp_root()
        try:
            local_appdata = temp_root / "localappdata"
            config_dir = local_appdata / "ListCompare"
            env_release_root = temp_root / "env-release-root"
            zip_path = temp_root / "artifacts" / "ListCompare-windows.zip"
            config_dir.mkdir(parents=True, exist_ok=True)
            env_release_root.mkdir(parents=True, exist_ok=True)
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            zip_path.write_text("zip payload", encoding="utf-8")
            (config_dir / "shared_sync_config.json").write_text("{ invalid json", encoding="utf-8")

            result = self._run_publish_script(
                version="2.0.0",
                zip_path=zip_path,
                local_appdata=local_appdata,
                env_release_root=env_release_root,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue((env_release_root / "ListCompare-windows-2.0.0.zip").exists())
            manifest = json.loads((env_release_root / "latest.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(manifest["version"], "2.0.0")
            self.assertEqual(manifest["zip"], "ListCompare-windows-2.0.0.zip")
        finally:
            if temp_root.exists():
                cleanup_temp_path(temp_root)


if __name__ == "__main__":
    unittest.main()
