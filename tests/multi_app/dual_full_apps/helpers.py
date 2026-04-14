import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from click.testing import CliRunner

from zodiac.main import cli


def generate_full_app(output_dir: Path, project_name: str, package_name: str = "app") -> Path:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "new",
            project_name,
            "--tpl",
            "standard-3tier",
            "-o",
            str(output_dir),
            "--package-name",
            package_name,
        ],
    )
    assert result.exit_code == 0, result.output
    return output_dir / project_name


def adapt_generated_app(project_dir: Path, table_name: str, cache_prefix: str, database_url: str) -> None:
    for file_path in project_dir.rglob("*.py"):
        content = file_path.read_text()
        content = content.replace('__tablename__ = "items"', f'__tablename__ = "{table_name}"')
        content = content.replace(
            "        timeout=config.github.timeout.as_float(),\n    )",
            "        timeout=config.github.timeout.as_float(),\n        trust_env=False,\n    )",
        )
        file_path.write_text(content)

    for config_path in (project_dir / "config").glob("*.ini"):
        lines = []
        for line in config_path.read_text().splitlines():
            if line.startswith("url = sqlite+aiosqlite:///./data.db"):
                lines.append(f"url = {database_url}")
            elif line.startswith("prefix = "):
                lines.append(f"prefix = {cache_prefix}")
            else:
                lines.append(line)
        config_path.write_text("\n".join(lines) + "\n")


def use_local_zodiac_core_dependency(project_dir: Path, repo_root: Path) -> None:
    pyproject_path = project_dir / "pyproject.toml"
    content = pyproject_path.read_text()
    content = content.replace(
        '"zodiac-core[sql,cache]"',
        f'"zodiac-core[sql,cache] @ {repo_root.resolve().as_uri()}"',
    )
    pyproject_path.write_text(content)


def write_multi_app_server(workspace_dir: Path, service_a_dir: Path, service_b_dir: Path) -> Path:
    server_path = workspace_dir / "server.py"
    server_path.write_text(
        f"""from contextlib import AsyncExitStack, asynccontextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from fastapi import FastAPI


ROOT = Path(__file__).resolve().parent
SERVICE_A_DIR = ROOT / "{service_a_dir.name}"
SERVICE_B_DIR = ROOT / "{service_b_dir.name}"


def load_app(project_dir: Path, module_name: str):
    sys.path.insert(0, str(project_dir))
    try:
        spec = spec_from_file_location(module_name, project_dir / "main.py")
        module = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module.app
    finally:
        sys.path.pop(0)


app_a = load_app(SERVICE_A_DIR, "service_a_main")
app_b = load_app(SERVICE_B_DIR, "service_b_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(app_a.router.lifespan_context(app_a))
        await stack.enter_async_context(app_b.router.lifespan_context(app_b))
        yield


app = FastAPI(title="multi-app-server", lifespan=lifespan)
app.mount("/a", app_a)
app.mount("/b", app_b)
"""
    )
    return server_path


@dataclass
class StartedServer:
    process: subprocess.Popen[str]
    base_url: str
    workspace_dir: Path
    app_a_dir: Path
    app_b_dir: Path
    server_path: Path
    db_path: Path
    stderr_path: Path
    stdout_path: Path


def build_dual_full_apps_server(workspace_dir: Path) -> tuple[Path, Path, Path, Path]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    db_path = workspace_dir / "multi_app.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    app_a_dir = generate_full_app(workspace_dir, "app_a", package_name="svc_a")
    app_b_dir = generate_full_app(workspace_dir, "app_b", package_name="svc_b")

    adapt_generated_app(
        app_a_dir,
        table_name="items_a",
        cache_prefix="multi_app_shared",
        database_url=database_url,
    )
    adapt_generated_app(
        app_b_dir,
        table_name="items_b",
        cache_prefix="multi_app_shared",
        database_url=database_url,
    )

    server_path = write_multi_app_server(workspace_dir, app_a_dir, app_b_dir)
    return app_a_dir, app_b_dir, server_path, db_path


def start_dual_full_apps_server(workspace_dir: Path, port: int, repo_root: Path) -> StartedServer:
    app_a_dir, app_b_dir, server_path, db_path = build_dual_full_apps_server(workspace_dir)
    stdout_path = workspace_dir / "server.stdout.log"
    stderr_path = workspace_dir / "server.stderr.log"
    use_local_zodiac_core_dependency(app_a_dir, repo_root)
    use_local_zodiac_core_dependency(app_b_dir, repo_root)

    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        env.pop(key, None)
        env.pop(key.lower(), None)

    sync = subprocess.run(
        ["uv", "sync", "--project", str(app_a_dir), "--extra", "dev", "--reinstall-package", "zodiac-core"],
        cwd=workspace_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if sync.returncode != 0:
        raise AssertionError(f"uv sync failed:\nstdout:\n{sync.stdout}\nstderr:\n{sync.stderr}")

    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(app_a_dir),
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=workspace_dir,
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    stdout_handle.close()
    stderr_handle.close()

    started = StartedServer(
        process=process,
        base_url=f"http://127.0.0.1:{port}",
        workspace_dir=workspace_dir,
        app_a_dir=app_a_dir,
        app_b_dir=app_b_dir,
        server_path=server_path,
        db_path=db_path,
        stderr_path=stderr_path,
        stdout_path=stdout_path,
    )
    wait_for_server_ready(started)
    return started


def stop_dual_full_apps_server(started: StartedServer) -> None:
    if started.process.poll() is not None:
        return

    started.process.terminate()
    try:
        started.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        started.process.kill()
        started.process.wait(timeout=5)


def wait_for_server_ready(started: StartedServer, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: str | None = None

    while time.time() < deadline:
        return_code = started.process.poll()
        if return_code is not None:
            raise AssertionError(
                "generated multi-app server exited before becoming ready:\n"
                f"stdout:\n{started.stdout_path.read_text(encoding='utf-8')}\n"
                f"stderr:\n{started.stderr_path.read_text(encoding='utf-8')}"
            )

        try:
            with httpx.Client(base_url=started.base_url, timeout=1.0) as client:
                health_a = client.get("/a/api/v1/health")
                health_b = client.get("/b/api/v1/health")
            if health_a.status_code == 200 and health_b.status_code == 200:
                return
            last_error = f"health status: a={health_a.status_code}, b={health_b.status_code}"
        except Exception as exc:  # pragma: no cover - startup timing dependent
            last_error = repr(exc)

        time.sleep(0.2)

    raise AssertionError(
        "generated multi-app server did not become ready in time"
        f"\nlast_error: {last_error}"
        f"\nstdout:\n{started.stdout_path.read_text(encoding='utf-8')}"
        f"\nstderr:\n{started.stderr_path.read_text(encoding='utf-8')}"
    )


def read_json_logs(log_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not log_path.exists():
        return records

    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        record = payload.get("record")
        if isinstance(record, dict):
            records.append(record)
    return records
