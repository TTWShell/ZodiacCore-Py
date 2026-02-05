"""Tests for verifying package build includes all required files."""

import subprocess
import zipfile
from pathlib import Path


class TestPackageBuild:
    """Tests for verifying package build completeness."""

    # Manually verified expected file counts
    EXPECTED_ZODIAC_FILES = 30  # Python files + template files (.jinja)
    EXPECTED_ZODIAC_CORE_FILES = 16  # Python files only

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

        # 3. Extract and count files in the wheel (separately for each package)
        actual_zodiac_files = self._count_wheel_files(wheel_path, "zodiac")
        actual_zodiac_core_files = self._count_wheel_files(wheel_path, "zodiac_core")

        # 4. Verify counts match manually verified expectations
        assert actual_zodiac_files == self.EXPECTED_ZODIAC_FILES, (
            f"zodiac file count mismatch: "
            f"expected={self.EXPECTED_ZODIAC_FILES} (manually verified), "
            f"actual={actual_zodiac_files}"
        )
        assert actual_zodiac_core_files == self.EXPECTED_ZODIAC_CORE_FILES, (
            f"zodiac_core file count mismatch: "
            f"expected={self.EXPECTED_ZODIAC_CORE_FILES} (manually verified), "
            f"actual={actual_zodiac_core_files}"
        )

    def _count_wheel_files(self, wheel_path: Path, package_name: str) -> int:
        """Count files for a specific package in the wheel."""
        count = 0
        with zipfile.ZipFile(wheel_path, "r") as wheel:
            for name in wheel.namelist():
                # Count files in the package directory
                if name.startswith(f"{package_name}/") and not name.endswith("/"):
                    # Exclude metadata files and dist-info
                    if not any(
                        excluded in name
                        for excluded in (
                            ".egg-info/",
                            ".dist-info/",
                            "__pycache__/",
                        )
                    ):
                        count += 1
        return count
