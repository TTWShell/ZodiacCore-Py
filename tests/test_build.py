"""Tests for verifying package build includes all required files."""

import subprocess
import zipfile
from pathlib import Path


class TestPackageBuild:
    """Tests for verifying package build completeness."""

    # Intentionally manual: adding or removing packaged files requires review.
    EXPECTED_PACKAGE_FILE_COUNTS = {
        "zodiac": 80,  # 14 Python files + 66 .jinja template files
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
        return {
            path.relative_to(project_root).as_posix()
            for path in package_root.rglob("*")
            if path.is_file() and (path.suffix == ".py" or path.name.endswith(".jinja"))
        }

    def _wheel_package_files(self, wheel_path: Path, package_name: str) -> set[str]:
        """Return files included for one package in the built wheel."""
        with zipfile.ZipFile(wheel_path, "r") as wheel:
            return {
                name
                for name in wheel.namelist()
                if name.startswith(f"{package_name}/") and not name.endswith("/") and "__pycache__/" not in name
            }
