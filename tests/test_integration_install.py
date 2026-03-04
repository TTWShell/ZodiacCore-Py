import glob
import os
import subprocess
import sys
from pathlib import Path

import pytest


def create_uv_venv(venv_path: Path):
    """Create a virtual environment using uv."""
    subprocess.run(["uv", "venv", str(venv_path)], check=True, capture_output=True)
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def run_in_venv(python_exe: Path, code: str, cwd: Path = None):
    """Run python code within the virtual environment."""
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(python_exe), "-c", code], capture_output=True, text=True, cwd=str(cwd) if cwd else None, env=env
    )


def venv_pip_install(python_exe: Path, args: list[str]):
    """Install packages into the venv using uv pip install."""
    venv_dir = python_exe.parent.parent
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_dir)
    subprocess.run(["uv", "pip", "install"] + args, check=True, capture_output=True, env=env)


class TestOptionalDependencies:
    """Integration tests to verify dependency isolation and optional features."""

    @pytest.fixture(scope="session")
    def built_wheel(self):
        """Build the wheel automatically before running integration tests."""
        project_root = Path(__file__).parent.parent
        # Ensure a fresh build of the current source code
        subprocess.run(["uv", "build"], cwd=str(project_root), check=True, capture_output=True)

        wheels = glob.glob(str(project_root / "dist" / "*.whl"))
        if not wheels:
            pytest.fail("Build failed: no wheel file generated in dist/")

        # Return the most recently created wheel
        latest_wheel = max(wheels, key=os.path.getmtime)
        return Path(latest_wheel)

    def test_install_core_only(self, built_wheel, tmp_path):
        """Verify that core modules work without SQL dependencies and fail gracefully."""
        venv_dir = tmp_path / "venv_core"
        python_exe = create_uv_venv(venv_dir)

        # 1. Install core wheel only
        venv_pip_install(python_exe, [str(built_wheel.absolute())])

        # 2. Verify core module is importable
        res = run_in_venv(python_exe, "import zodiac_core; print(zodiac_core.__version__)")
        assert res.returncode == 0, res.stderr

        # 3. Verify importing db module fails with helpful guidance (no sqlmodel present)
        res = run_in_venv(python_exe, "from zodiac_core.db import sql")
        assert res.returncode != 0
        assert "SQLModel and SQLAlchemy[asyncio] are required" in res.stderr
        assert "pip install 'zodiac-core[sql]'" in res.stderr

        # 4. Verify importing cache module fails with helpful guidance (no aiocache)
        res = run_in_venv(python_exe, "from zodiac_core.cache import cache")
        assert res.returncode != 0
        assert "aiocache is required" in res.stderr
        assert "pip install 'zodiac-core[cache]'" in res.stderr

    def test_install_sql_extra(self, built_wheel, tmp_path):
        """Verify that SQL features work when [sql] extra is installed."""
        venv_dir = tmp_path / "venv_sql"
        python_exe = create_uv_venv(venv_dir)

        # 1. Install wheel with [sql] extra
        venv_pip_install(python_exe, [f"{built_wheel.absolute()}[sql]"])

        # 2. Verify db module is importable
        res = run_in_venv(python_exe, "from zodiac_core.db import sql; print('Import OK')")
        assert res.returncode == 0, res.stderr
        assert "Import OK" in res.stdout

    def test_install_mongo_extra(self, built_wheel, tmp_path):
        """Verify that Mongo features work when [mongo] extra is installed."""
        venv_dir = tmp_path / "venv_mongo"
        python_exe = create_uv_venv(venv_dir)

        # 1. Install wheel with [mongo] extra
        venv_pip_install(python_exe, [f"{built_wheel.absolute()}[mongo]"])

        # 2. Verify motor is importable
        res = run_in_venv(python_exe, "import motor; print('Motor OK')")
        assert res.returncode == 0, res.stderr
        assert "Motor OK" in res.stdout

    def test_install_cache_extra(self, built_wheel, tmp_path):
        """Verify that cache features work when [cache] extra is installed."""
        venv_dir = tmp_path / "venv_cache"
        python_exe = create_uv_venv(venv_dir)

        # 1. Install wheel with [cache] extra
        venv_pip_install(python_exe, [f"{built_wheel.absolute()}[cache]"])

        # 2. Verify cache module is importable and setup/cache work
        code = """
import asyncio
from zodiac_core.cache import cache, cached, ZodiacCache

cache.setup(prefix="test", default_ttl=60)
c = cache.cache
assert c is not None
asyncio.run(c.set("k", 1))
assert asyncio.run(c.get("k")) == 1
print("Cache OK")
"""
        res = run_in_venv(python_exe, code)
        assert res.returncode == 0, (res.stdout or "") + (res.stderr or "")
        assert "Cache OK" in (res.stdout or "")
