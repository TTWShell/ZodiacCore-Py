"""Tests for `zodiac skills install` and `zodiac skills uninstall`."""

from __future__ import annotations

from pathlib import Path

import pytest
from click import ClickException

from zodiac.commands.skills import (
    AGENT_SKILL_DIRS,
    GITIGNORE_HEADER,
    _already_linked,
    _is_link,
    gitignore_pattern,
    packaged_skills_root,
    resolve_agents,
)
from zodiac.main import cli


@pytest.fixture
def project_path(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'example'\n", encoding="utf-8")
    return tmp_path


class TestSkillsInstall:
    def test_help(self, cli_runner):
        result = cli_runner.invoke(cli, ["skills", "install", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output
        assert "codex" in result.output
        assert "symlink" in result.output.lower() or "junction" in result.output.lower()

    def test_links_packaged_skills_and_gitignores_them(self, cli_runner, project_path):
        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code == 0, result.output

        docs = project_path / ".agents" / "skills" / "zodiac-docs"
        summary = project_path / ".agents" / "skills" / "zodiac-core-integration-summary"
        assert _is_link(docs)
        assert _is_link(summary)
        assert docs.resolve() == (packaged_skills_root() / "zodiac-docs").resolve()
        assert (docs / "SKILL.md").is_file()
        assert gitignore_pattern("codex") in (project_path / ".gitignore").read_text(encoding="utf-8")
        assert "linked" in result.output
        assert (project_path / ".claude" / "skills" / "zodiac-docs").exists() is False

    def test_agent_claude_uses_claude_directory(self, cli_runner, project_path):
        result = cli_runner.invoke(cli, ["skills", "install", "--agent", "claude", str(project_path)])
        assert result.exit_code == 0, result.output
        docs = project_path / ".claude" / "skills" / "zodiac-docs"
        assert _is_link(docs)
        assert docs.resolve() == (packaged_skills_root() / "zodiac-docs").resolve()
        assert not (project_path / ".agents" / "skills" / "zodiac-docs").exists()
        ignore = (project_path / ".gitignore").read_text(encoding="utf-8")
        assert gitignore_pattern("claude") in ignore
        assert gitignore_pattern("codex") not in ignore

    def test_multiple_agents(self, cli_runner, project_path):
        result = cli_runner.invoke(
            cli,
            ["skills", "install", "--agent", "codex", "--agent", "copilot", str(project_path)],
        )
        assert result.exit_code == 0, result.output
        assert _is_link(project_path / ".agents" / "skills" / "zodiac-docs")
        assert _is_link(project_path / ".github" / "skills" / "zodiac-docs")
        ignore = (project_path / ".gitignore").read_text(encoding="utf-8")
        assert gitignore_pattern("codex") in ignore
        assert gitignore_pattern("copilot") in ignore

    def test_agent_all_installs_every_directory(self, cli_runner, project_path):
        result = cli_runner.invoke(cli, ["skills", "install", "--agent", "all", str(project_path)])
        assert result.exit_code == 0, result.output
        ignore = (project_path / ".gitignore").read_text(encoding="utf-8")
        for agent, relative in AGENT_SKILL_DIRS.items():
            assert _is_link(project_path / relative / "zodiac-docs")
            assert gitignore_pattern(agent) in ignore

    def test_second_install_is_unchanged(self, cli_runner, project_path):
        first = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert first.exit_code == 0, first.output
        second = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert second.exit_code == 0, second.output
        assert "unchanged" in second.output

    def test_gitignore_is_idempotent(self, cli_runner, project_path):
        first = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert first.exit_code == 0, first.output
        ignore = (project_path / ".gitignore").read_text(encoding="utf-8")
        second = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert second.exit_code == 0, second.output
        assert (project_path / ".gitignore").read_text(encoding="utf-8") == ignore
        assert ignore.count(GITIGNORE_HEADER) == 1
        assert ignore.count(gitignore_pattern("codex")) == 1

    def test_replaces_stale_link_without_force(self, cli_runner, project_path):
        dest = project_path / ".agents" / "skills" / "zodiac-docs"
        dest.parent.mkdir(parents=True)
        old = project_path / "old-skill"
        old.mkdir()
        dest.symlink_to(old, target_is_directory=True)

        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code == 0, result.output
        assert _is_link(dest)
        assert dest.resolve() == (packaged_skills_root() / "zodiac-docs").resolve()
        assert "linked" in result.output

    def test_replaces_broken_link_without_force(self, cli_runner, project_path):
        dest = project_path / ".agents" / "skills" / "zodiac-docs"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(project_path / "missing-skill", target_is_directory=True)

        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code == 0, result.output
        assert _is_link(dest)
        assert dest.resolve() == (packaged_skills_root() / "zodiac-docs").resolve()

    def test_existing_directory_requires_force(self, cli_runner, project_path):
        dest = project_path / ".agents" / "skills" / "zodiac-docs"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("stale\n", encoding="utf-8")

        blocked = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert blocked.exit_code != 0
        assert "--force" in blocked.output

        replaced = cli_runner.invoke(cli, ["skills", "install", "--force", str(project_path)])
        assert replaced.exit_code == 0, replaced.output
        assert _is_link(project_path / ".agents" / "skills" / "zodiac-docs")

    def test_installs_at_project_root_from_subdirectory(self, cli_runner, project_path):
        nested = project_path / "app" / "api"
        nested.mkdir(parents=True)
        result = cli_runner.invoke(cli, ["skills", "install", str(nested)])
        assert result.exit_code == 0, result.output
        assert _is_link(project_path / ".agents" / "skills" / "zodiac-docs")
        assert gitignore_pattern("codex") in (project_path / ".gitignore").read_text(encoding="utf-8")
        assert not (nested / ".agents").exists()
        assert not (nested / ".gitignore").exists()

    def test_installs_at_project_root_from_cwd(self, cli_runner, project_path, monkeypatch):
        nested = project_path / "app"
        nested.mkdir()
        monkeypatch.chdir(nested)
        result = cli_runner.invoke(cli, ["skills", "install"])
        assert result.exit_code == 0, result.output
        assert _is_link(project_path / ".agents" / "skills" / "zodiac-docs")
        assert not (nested / ".agents").exists()

    def test_missing_pyproject_errors(self, cli_runner, tmp_path):
        result = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert result.exit_code != 0
        assert "pyproject.toml" in result.output
        assert not (tmp_path / ".agents").exists()

    def test_unix_failure_hint(self, cli_runner, project_path, monkeypatch):
        def fail(*_args, **_kwargs):
            raise OSError(1, "operation not permitted")

        monkeypatch.setattr("zodiac.commands.skills.sys.platform", "linux")
        monkeypatch.setattr("zodiac.commands.skills.os.symlink", fail)
        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code != 0
        assert "symlink" in result.output.lower()
        assert "filesystem allows symbolic links" in result.output

    def test_windows_failure_hint(self, cli_runner, project_path, monkeypatch):
        from types import SimpleNamespace

        def fail(*_args, **_kwargs):
            raise OSError(1314, "A required privilege is not held by the client")

        monkeypatch.setattr("zodiac.commands.skills.sys.platform", "win32")
        monkeypatch.setitem(__import__("sys").modules, "_winapi", SimpleNamespace(CreateJunction=fail))
        monkeypatch.setattr("zodiac.commands.skills.os.symlink", fail)
        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code != 0
        assert "junction" in result.output.lower()
        assert "Developer Mode" in result.output

    def test_windows_leftover_directory_falls_back_to_symlink(self, cli_runner, project_path, monkeypatch):
        from types import SimpleNamespace

        calls = {"n": 0}

        def create_junction(src, dst):
            calls["n"] += 1
            if calls["n"] == 1:
                Path(dst).symlink_to(src, target_is_directory=True)
                return
            Path(dst).mkdir(parents=True, exist_ok=True)
            raise OSError(1, "failed after creating the destination")

        monkeypatch.setattr("zodiac.commands.skills.sys.platform", "win32")
        monkeypatch.setitem(__import__("sys").modules, "_winapi", SimpleNamespace(CreateJunction=create_junction))
        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code == 0, result.output
        assert "junction" in result.output
        assert "symlink" in result.output
        assert _is_link(project_path / ".agents" / "skills" / "zodiac-docs")

    @pytest.mark.parametrize(
        ("create_empty", "needle"),
        [
            (False, "Packaged skills were not found"),
            (True, "No SKILL.md"),
        ],
    )
    def test_packaged_skills_unavailable(self, cli_runner, project_path, tmp_path, monkeypatch, create_empty, needle):
        root = tmp_path / "skills-root"
        if create_empty:
            root.mkdir()
        monkeypatch.setattr("zodiac.commands.skills.packaged_skills_root", lambda: root)
        result = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert result.exit_code != 0
        assert needle in result.output

    def test_unknown_agent_and_unreadable_link(self, tmp_path, monkeypatch):
        with pytest.raises(ClickException, match="Unknown agent"):
            resolve_agents(("nope",))

        source = tmp_path / "src"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.symlink_to(source, target_is_directory=True)

        def fail(self, *_args, **_kwargs):
            raise OSError(1, "fail")

        monkeypatch.setattr(Path, "resolve", fail)
        assert _already_linked(dest, source) is False


class TestSkillsUninstall:
    def test_help(self, cli_runner):
        result = cli_runner.invoke(cli, ["skills", "uninstall", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output
        assert "--force" in result.output

    def test_removes_links_and_gitignore(self, cli_runner, project_path):
        installed = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert installed.exit_code == 0, installed.output

        result = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert result.exit_code == 0, result.output
        assert "removed" in result.output
        assert not (project_path / ".agents" / "skills" / "zodiac-docs").exists()
        assert not (project_path / ".agents" / "skills" / "zodiac-core-integration-summary").exists()
        assert not (project_path / ".agents").exists()
        assert not (project_path / ".gitignore").exists()

    def test_leaves_other_skills_and_user_gitignore(self, cli_runner, project_path):
        (project_path / ".gitignore").write_text(".venv\n", encoding="utf-8")
        custom = project_path / ".agents" / "skills" / "my-skill"
        custom.mkdir(parents=True)
        (custom / "SKILL.md").write_text("custom\n", encoding="utf-8")
        installed = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert installed.exit_code == 0, installed.output

        result = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert result.exit_code == 0, result.output
        assert (custom / "SKILL.md").is_file()
        ignore = (project_path / ".gitignore").read_text(encoding="utf-8")
        assert ".venv" in ignore
        assert gitignore_pattern("codex") not in ignore
        assert GITIGNORE_HEADER not in ignore

    def test_default_agent_does_not_remove_other_agents(self, cli_runner, project_path):
        installed = cli_runner.invoke(
            cli,
            ["skills", "install", "--agent", "codex", "--agent", "claude", str(project_path)],
        )
        assert installed.exit_code == 0, installed.output

        result = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert result.exit_code == 0, result.output
        assert not (project_path / ".agents" / "skills" / "zodiac-docs").exists()
        assert _is_link(project_path / ".claude" / "skills" / "zodiac-docs")
        ignore = (project_path / ".gitignore").read_text(encoding="utf-8")
        assert gitignore_pattern("codex") not in ignore
        assert gitignore_pattern("claude") in ignore

    def test_agent_all(self, cli_runner, project_path):
        installed = cli_runner.invoke(cli, ["skills", "install", "--agent", "all", str(project_path)])
        assert installed.exit_code == 0, installed.output
        result = cli_runner.invoke(cli, ["skills", "uninstall", "--agent", "all", str(project_path)])
        assert result.exit_code == 0, result.output
        for relative in AGENT_SKILL_DIRS.values():
            assert not (project_path / relative / "zodiac-docs").exists()
        assert not (project_path / ".gitignore").exists()

    def test_copied_directory_requires_force(self, cli_runner, project_path):
        dest = project_path / ".agents" / "skills" / "zodiac-docs"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("copied\n", encoding="utf-8")
        copied_file = project_path / ".agents" / "skills" / "zodiac-core-integration-summary"
        copied_file.write_text("copied file\n", encoding="utf-8")

        blocked = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert blocked.exit_code != 0
        assert "--force" in blocked.output
        assert (dest / "SKILL.md").read_text(encoding="utf-8") == "copied\n"
        assert copied_file.read_text(encoding="utf-8") == "copied file\n"

        removed = cli_runner.invoke(cli, ["skills", "uninstall", "--force", str(project_path)])
        assert removed.exit_code == 0, removed.output
        assert not dest.exists()
        assert not copied_file.exists()

    def test_second_uninstall_is_absent(self, cli_runner, project_path):
        installed = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert installed.exit_code == 0, installed.output
        first = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert first.exit_code == 0, first.output
        second = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert second.exit_code == 0, second.output
        assert "absent" in second.output

    def test_walks_up_from_subdirectory(self, cli_runner, project_path):
        installed = cli_runner.invoke(cli, ["skills", "install", str(project_path)])
        assert installed.exit_code == 0, installed.output
        nested = project_path / "app" / "api"
        nested.mkdir(parents=True)
        result = cli_runner.invoke(cli, ["skills", "uninstall", str(nested)])
        assert result.exit_code == 0, result.output
        assert not (project_path / ".agents" / "skills" / "zodiac-docs").exists()

    def test_missing_pyproject_errors(self, cli_runner, tmp_path):
        result = cli_runner.invoke(cli, ["skills", "uninstall", str(tmp_path)])
        assert result.exit_code != 0
        assert "pyproject.toml" in result.output

    def test_leaves_unrelated_gitignore_unchanged(self, cli_runner, project_path):
        gitignore = project_path / ".gitignore"
        gitignore.write_text(".venv\n", encoding="utf-8")
        skills_dir = project_path / ".agents" / "skills"
        skills_dir.parent.mkdir()
        skills_dir.write_text("not a directory\n", encoding="utf-8")
        result = cli_runner.invoke(cli, ["skills", "uninstall", str(project_path)])
        assert result.exit_code == 0, result.output
        assert gitignore.read_text(encoding="utf-8") == ".venv\n"
        assert "updated" not in result.output
        assert skills_dir.is_file()
