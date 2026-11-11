"""Every shipped UI template must compile in Django."""

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class TemplateCompilationTests(SimpleTestCase):
    def test_all_templates_compile(self):
        root = Path(settings.BASE_DIR) / "templates"
        errors = {}
        for path in root.rglob("*.html"):
            name = path.relative_to(root).as_posix()
            try:
                get_template(name)
            except Exception as exc:
                errors[name] = str(exc)

        self.assertFalse(errors, f"Broken UI templates: {errors}")
