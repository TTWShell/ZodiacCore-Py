import sqlite3
import time
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.multi_app.dual_full_apps.helpers import (
    read_json_logs,
    start_dual_full_apps_server,
    stop_dual_full_apps_server,
)


@pytest.mark.serial
class TestDualFullApps:
    @pytest.fixture(scope="class")
    def generated_apps_root(self, tmp_path_factory):
        return tmp_path_factory.mktemp("multi_app_generated")

    @pytest.fixture(scope="class")
    def generated_dual_app_server(self, generated_apps_root, unused_tcp_port_factory):
        port = unused_tcp_port_factory()
        repo_root = Path(__file__).resolve().parents[3]
        started = start_dual_full_apps_server(generated_apps_root, port=port, repo_root=repo_root)

        yield started

        stop_dual_full_apps_server(started)

    @pytest.mark.asyncio
    async def test_dual_generated_apps_build_a_complete_unified_server(self, generated_dual_app_server):
        assert generated_dual_app_server.app_a_dir.exists()
        assert generated_dual_app_server.app_b_dir.exists()
        assert (generated_dual_app_server.app_a_dir / "main.py").exists()
        assert (generated_dual_app_server.app_b_dir / "main.py").exists()
        assert (generated_dual_app_server.app_a_dir / "svc_a").is_dir()
        assert (generated_dual_app_server.app_b_dir / "svc_b").is_dir()
        assert generated_dual_app_server.server_path.exists()

        server_source = generated_dual_app_server.server_path.read_text()
        assert 'app.mount("/a", app_a)' in server_source
        assert 'app.mount("/b", app_b)' in server_source

    @pytest.mark.parametrize("mount_prefix", ["a", "b"])
    @pytest.mark.asyncio
    async def test_mounted_app_keeps_zodiac_contracts(self, generated_dual_app_server, mount_prefix):
        async with AsyncClient(base_url=generated_dual_app_server.base_url) as client:
            health = await client.get(f"/{mount_prefix}/api/v1/health")
            items = await client.get(f"/{mount_prefix}/api/v1/items?page=1&size=20")
            missing_item = await client.get(f"/{mount_prefix}/api/v1/items/1")

        assert health.status_code == 200
        assert health.headers["X-Request-ID"]
        assert health.json() == {
            "code": 0,
            "message": "Success",
            "data": {"status": "healthy"},
        }

        assert items.status_code == 200
        assert items.headers["X-Request-ID"]
        assert items.json() == {
            "code": 0,
            "message": "Success",
            "data": {
                "items": [],
                "total": 0,
                "page": 1,
                "size": 20,
            },
        }

        assert missing_item.status_code == 404
        assert missing_item.headers["X-Request-ID"]
        assert missing_item.json() == {
            "code": 404,
            "message": "Item id '1' not found",
            "data": None,
        }

    @pytest.mark.asyncio
    async def test_mounted_apps_keep_independent_request_ids_and_tables(self, generated_dual_app_server):
        async with AsyncClient(base_url=generated_dual_app_server.base_url) as client:
            response_a = await client.get("/a/api/v1/health")
            response_b = await client.get("/b/api/v1/health")

        assert response_a.headers["X-Request-ID"] != response_b.headers["X-Request-ID"]
        with sqlite3.connect(generated_dual_app_server.db_path) as conn:
            table_names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "items_a" in table_names
        assert "items_b" in table_names
        assert "items" not in table_names

    @pytest.mark.asyncio
    async def test_mounted_apps_keep_database_rows_isolated_by_app_table(self, generated_dual_app_server):
        with sqlite3.connect(generated_dual_app_server.db_path) as conn:
            conn.execute("DELETE FROM items_a")
            conn.execute("DELETE FROM items_b")
            conn.commit()
            conn.execute("INSERT INTO items_a (name, description) VALUES (?, ?)", ("app-a-only", "stored in app a"))
            conn.commit()

        async with AsyncClient(base_url=generated_dual_app_server.base_url) as client:
            list_a_after_a_insert = await client.get("/a/api/v1/items?page=1&size=20")
            list_b_after_a_insert = await client.get("/b/api/v1/items?page=1&size=20")

        with sqlite3.connect(generated_dual_app_server.db_path) as conn:
            conn.execute("INSERT INTO items_b (name, description) VALUES (?, ?)", ("app-b-only", "stored in app b"))
            conn.commit()

        async with AsyncClient(base_url=generated_dual_app_server.base_url) as client:
            list_a_after_b_insert = await client.get("/a/api/v1/items?page=1&size=20")
            list_b_after_b_insert = await client.get("/b/api/v1/items?page=1&size=20")

        with sqlite3.connect(generated_dual_app_server.db_path) as conn:
            conn.execute("DELETE FROM items_a")
            conn.execute("DELETE FROM items_b")
            conn.commit()

        assert [item["name"] for item in list_a_after_a_insert.json()["data"]["items"]] == ["app-a-only"]
        assert list_b_after_a_insert.json()["data"]["items"] == []
        assert [item["name"] for item in list_a_after_b_insert.json()["data"]["items"]] == ["app-a-only"]
        assert [item["name"] for item in list_b_after_b_insert.json()["data"]["items"]] == ["app-b-only"]

    @pytest.mark.asyncio
    async def test_mounted_apps_initialize_shared_cache_resource(self, generated_dual_app_server):
        log_records = self._wait_for_log_records(
            generated_dual_app_server.stderr_path,
            predicate=lambda records: any(
                "Cache 'default' initialized with prefix=multi_app_shared" in record.get("message", "")
                for record in records
            ),
        )
        cache_logs = [
            record["message"]
            for record in log_records
            if "Cache 'default' initialized with prefix=multi_app_shared" in record["message"]
        ]
        assert len(cache_logs) >= 1

    @pytest.mark.asyncio
    async def test_mounted_apps_keep_app_service_names_in_logs(self, generated_dual_app_server):
        async with AsyncClient(base_url=generated_dual_app_server.base_url) as client:
            await client.get("/a/api/v1/health")
            await client.get("/b/api/v1/health")

        log_records = self._wait_for_log_records(
            generated_dual_app_server.stderr_path,
            predicate=lambda records: any(
                record.get("message", "").startswith("GET /a/api/v1/health")
                or record.get("message", "").startswith("GET /b/api/v1/health")
                for record in records
            ),
        )
        access_logs = {
            record["extra"]["path"]: record["extra"]["service"]
            for record in log_records
            if record["message"].startswith("GET ")
        }

        assert access_logs["/a/api/v1/health"] == "app_a"
        assert access_logs["/b/api/v1/health"] == "app_b"

    def _wait_for_log_records(self, log_path, predicate=None, timeout=5.0):
        deadline = time.time() + timeout
        predicate = predicate or (lambda records: len(records) > 0)

        while time.time() < deadline:
            records = read_json_logs(log_path)
            if predicate(records):
                return records
            time.sleep(0.1)

        return read_json_logs(log_path)
