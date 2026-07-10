from pathlib import Path

import pytest
from jinja2 import UndefinedError

from zodiac.commands.rendering import RenderedFile, build_render_plan, write_render_plan


class TestBuildRenderPlan:
    def test_renders_templates_with_default_path_mapping(self, tmp_path):
        template_root = tmp_path / "templates"
        template_root.mkdir()
        (template_root / "example.txt.jinja").write_text("Hello, {{ name }}!\n", encoding="utf-8")

        plan = build_render_plan(
            template_path=template_root,
            destination_root=tmp_path / "output",
            context={"name": "Zodiac"},
        )

        assert plan == [
            RenderedFile(
                destination=tmp_path / "output" / "example.txt",
                content="Hello, Zodiac!\n",
            )
        ]

    def test_rejects_duplicate_mapped_destinations(self, tmp_path):
        template_root = tmp_path / "templates"
        template_root.mkdir()
        (template_root / "first.jinja").write_text("first", encoding="utf-8")
        (template_root / "second.jinja").write_text("second", encoding="utf-8")

        with pytest.raises(ValueError, match="Multiple templates render to the same file"):
            build_render_plan(
                template_path=template_root,
                destination_root=tmp_path / "output",
                context={},
                path_mapper=lambda _path: Path("duplicate.txt"),
            )

    def test_rejects_missing_template_context(self, tmp_path):
        template_root = tmp_path / "templates"
        template_root.mkdir()
        (template_root / "example.jinja").write_text("{{ required }}", encoding="utf-8")

        with pytest.raises(UndefinedError):
            build_render_plan(
                template_path=template_root,
                destination_root=tmp_path / "output",
                context={},
            )


class TestWriteRenderPlan:
    def test_rolls_back_overwrites_and_created_paths(self, tmp_path, monkeypatch):
        existing = tmp_path / "existing.txt"
        existing.write_text("original", encoding="utf-8")
        created = tmp_path / "created" / "new.txt"
        failing = tmp_path / "blocked" / "failure.txt"
        original_write_text = Path.write_text

        def fail_final_write(path, content, *, encoding=None, errors=None, newline=None):
            if path == failing:
                original_write_text(path.parent / "keep.txt", "keep", encoding="utf-8")
                raise OSError("simulated write failure")
            return original_write_text(path, content, encoding=encoding, errors=errors, newline=newline)

        monkeypatch.setattr(Path, "write_text", fail_final_write)

        with pytest.raises(OSError, match="simulated write failure"):
            write_render_plan(
                [
                    RenderedFile(destination=existing, content="changed"),
                    RenderedFile(destination=created, content="created"),
                    RenderedFile(destination=failing, content="failure"),
                ],
                force=True,
            )

        assert existing.read_text(encoding="utf-8") == "original"
        assert not created.exists()
        assert not created.parent.exists()
        assert not failing.exists()
        assert (failing.parent / "keep.txt").read_text(encoding="utf-8") == "keep"
