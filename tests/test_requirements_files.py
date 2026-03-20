import unittest
from pathlib import Path


def _read_requirement_lines(path: str) -> list[str]:
    content = Path(path).read_text(encoding="utf-8")
    lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


class RequirementsFilesTests(unittest.TestCase):
    def test_runtime_requirements_are_exactly_pinned(self) -> None:
        lines = _read_requirement_lines("requirements.txt")
        self.assertGreater(len(lines), 0)
        self.assertTrue(all("==" in line for line in lines))

    def test_build_requirements_are_exactly_pinned(self) -> None:
        lines = _read_requirement_lines("requirements-build.txt")
        self.assertGreater(len(lines), 0)
        self.assertTrue(all("==" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
