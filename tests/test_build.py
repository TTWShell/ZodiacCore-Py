"""Tests for verifying package build includes all required files."""

import subprocess
import zipfile
from pathlib import Path


class TestPackageBuild:
    """Tests for verifying package build completeness."""

    # Intentionally manual: adding or removing packaged files requires review.
    EXPECTED_PACKAGE_FILE_COUNTS = {
        "zodiac": 87,  # 16 Python files (incl. one skill script) + 67 .jinja + 4 non-Python skill assets
        "zodiac_core": 20,  # Python files only
    }

    def test_build_includes_all_files(self, tmp_path):
        """Verify that built package includes all required files from zodiac and zodiac_core."""
        project_root = Path(__file__).parent.parent

        # 1. Build the package
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()

        result = subprocess.run(
            ["uv", "build", "--out-dir", str(dist_dir)],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"

        # 2. Find the built wheel
        wheel_files = list(dist_dir.glob("*.whl"))
        assert len(wheel_files) == 1, f"Expected 1 wheel file, found {len(wheel_files)}"

        wheel_path = wheel_files[0]

        # 3. Compare the exact source package files with the wheel contents.
        for package_name in ("zodiac", "zodiac_core"):
            source_files = self._source_package_files(project_root, package_name)
            expected_count = self.EXPECTED_PACKAGE_FILE_COUNTS[package_name]
            assert len(source_files) == expected_count, (
                f"{package_name} source file count mismatch: "
                f"expected={expected_count} (manually verified), actual={len(source_files)}"
            )

            wheel_files = self._wheel_package_files(wheel_path, package_name)
            assert wheel_files == source_files, (
                f"{package_name} wheel contents differ from source: "
                f"missing={sorted(source_files - wheel_files)}, unexpected={sorted(wheel_files - source_files)}"
            )

    def _source_package_files(self, project_root: Path, package_name: str) -> set[str]:
        """Return package files that must be present in the wheel."""
        package_root = project_root / package_name
        packaged = set()
        for path in package_root.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            is_skill_asset = self._is_packaged_skill_asset(path, package_root)
            if path.suffix == ".py" or path.name.endswith(".jinja") or is_skill_asset:
                packaged.add(path.relative_to(project_root).as_posix())
        return packaged

    @staticmethod
    def _is_packaged_skill_asset(path: Path, package_root: Path) -> bool:
        """Return True only for skill files shipped by the package-data globs."""
        try:
            parts = path.relative_to(package_root).parts
        except ValueError:
            return False
        if len(parts) < 3 or parts[0] != "skills":
            return False
        if "__pycache__" in parts or parts[1].startswith("."):
            return False
        site = parts[2]
        if len(parts) == 3 and site == "SKILL.md":
            return True
        if len(parts) == 4 and site in {"agents", "references"}:
            return True
        if len(parts) == 4 and site == "scripts" and path.suffix == ".py":
            return True
        return False

    def _wheel_package_files(self, wheel_path: Path, package_name: str) -> set[str]:
        """Return files included for one package in the built wheel."""
        with zipfile.ZipFile(wheel_path, "r") as wheel:
            return {
                name
                for name in wheel.namelist()
                if name.startswith(f"{package_name}/") and not name.endswith("/") and "__pycache__/" not in name
            }
