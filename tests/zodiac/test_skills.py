"""Tests for `zodiac skills install`."""

from __future__ import annotations

from zodiac.commands.skills import gitignore_pattern, packaged_skills_root
from zodiac.main import cli


class TestSkillsInstall:
    def test_help(self, cli_runner):
        result = cli_runner.invoke(cli, ["skills", "install", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output
        assert "codex" in result.output
        assert "symlink" in result.output.lower() or "junction" in result.output.lower()

    def test_links_packaged_skills_and_gitignores_them(self, cli_runner, tmp_path):
        result = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert result.exit_code == 0, result.output

        docs = tmp_path / ".agents" / "skills" / "zodiac-docs"
        summary = tmp_path / ".agents" / "skills" / "zodiac-core-integration-summary"
        assert docs.is_symlink()
        assert summary.is_symlink()
        assert docs.resolve() == (packaged_skills_root() / "zodiac-docs").resolve()
        assert (docs / "SKILL.md").is_file()
        assert gitignore_pattern("codex") in (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "linked" in result.output
        assert (tmp_path / ".claude" / "skills" / "zodiac-docs").exists() is False

    def test_agent_claude_uses_claude_directory(self, cli_runner, tmp_path):
        result = cli_runner.invoke(cli, ["skills", "install", "--agent", "claude", str(tmp_path)])
        assert result.exit_code == 0, result.output
        docs = tmp_path / ".claude" / "skills" / "zodiac-docs"
        assert docs.is_symlink()
        assert docs.resolve() == (packaged_skills_root() / "zodiac-docs").resolve()
        assert not (tmp_path / ".agents" / "skills" / "zodiac-docs").exists()
        ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert gitignore_pattern("claude") in ignore
        assert gitignore_pattern("codex") not in ignore

    def test_multiple_agents_and_all(self, cli_runner, tmp_path):
        result = cli_runner.invoke(
            cli,
            ["skills", "install", "--agent", "codex", "--agent", "copilot", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".agents" / "skills" / "zodiac-docs").is_symlink()
        assert (tmp_path / ".github" / "skills" / "zodiac-docs").is_symlink()
        ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert gitignore_pattern("codex") in ignore
        assert gitignore_pattern("copilot") in ignore

    def test_second_install_is_unchanged(self, cli_runner, tmp_path):
        first = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert first.exit_code == 0, first.output
        second = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert second.exit_code == 0, second.output
        assert "unchanged" in second.output

    def test_existing_directory_requires_force(self, cli_runner, tmp_path):
        dest = tmp_path / ".agents" / "skills" / "zodiac-docs"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("stale\n", encoding="utf-8")

        blocked = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert blocked.exit_code != 0
        assert "--force" in blocked.output

        replaced = cli_runner.invoke(cli, ["skills", "install", "--force", str(tmp_path)])
        assert replaced.exit_code == 0, replaced.output
        assert (tmp_path / ".agents" / "skills" / "zodiac-docs").is_symlink()

    def test_unix_failure_hint(self, cli_runner, tmp_path, monkeypatch):
        def fail(*_args, **_kwargs):
            raise OSError(1, "operation not permitted")

        monkeypatch.setattr("zodiac.commands.skills.sys.platform", "linux")
        monkeypatch.setattr("zodiac.commands.skills.os.symlink", fail)
        result = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert result.exit_code != 0
        assert "symlink" in result.output.lower()
        assert "filesystem allows symbolic links" in result.output

    def test_windows_failure_hint(self, cli_runner, tmp_path, monkeypatch):
        from types import SimpleNamespace

        def fail(*_args, **_kwargs):
            raise OSError(1314, "A required privilege is not held by the client")

        monkeypatch.setattr("zodiac.commands.skills.sys.platform", "win32")
        monkeypatch.setitem(__import__("sys").modules, "_winapi", SimpleNamespace(CreateJunction=fail))
        monkeypatch.setattr("zodiac.commands.skills.os.symlink", fail)
        result = cli_runner.invoke(cli, ["skills", "install", str(tmp_path)])
        assert result.exit_code != 0
        assert "junction" in result.output.lower()
        assert "Developer Mode" in result.output
