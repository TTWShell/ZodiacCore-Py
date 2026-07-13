from pathlib import Path

import pytest
from jinja2 import UndefinedError

from zodiac.commands.rendering import (
    RenderedFile,
    TemplatePathError,
    build_render_plan,
    write_render_plan,
)


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

    @pytest.mark.parametrize("mapped_destination", [Path("../outside.txt"), Path("nested/../../outside.txt")])
    def test_rejects_mapped_destinations_that_traverse_outside_root(self, tmp_path, mapped_destination):
        template_root = tmp_path / "templates"
        template_root.mkdir()
        (template_root / "example.jinja").write_text("example", encoding="utf-8")

        with pytest.raises(TemplatePathError, match="escapes its output directory"):
            build_render_plan(
                template_path=template_root,
                destination_root=tmp_path / "output",
                context={},
                path_mapper=lambda _path: mapped_destination,
            )

    def test_rejects_absolute_mapped_destinations_outside_root(self, tmp_path):
        template_root = tmp_path / "templates"
        template_root.mkdir()
        (template_root / "example.jinja").write_text("example", encoding="utf-8")

        with pytest.raises(TemplatePathError, match="escapes its output directory"):
            build_render_plan(
                template_path=template_root,
                destination_root=tmp_path / "output",
                context={},
                path_mapper=lambda _path: tmp_path / "outside.txt",
            )

    def test_rejects_destinations_reached_through_external_symlink(self, tmp_path):
        template_root = tmp_path / "templates"
        template_root.mkdir()
        (template_root / "example.jinja").write_text("example", encoding="utf-8")
        destination_root = tmp_path / "output"
        destination_root.mkdir()
        external_root = tmp_path / "external"
        external_root.mkdir()
        (destination_root / "linked").symlink_to(external_root, target_is_directory=True)

        with pytest.raises(TemplatePathError, match="escapes its output directory"):
            build_render_plan(
                template_path=template_root,
                destination_root=destination_root,
                context={},
                path_mapper=lambda _path: Path("linked/example.txt"),
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
