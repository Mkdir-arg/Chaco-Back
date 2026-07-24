from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TooltipAccessibilityTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR)
        self.base = (self.root / "templates/includes/base.html").read_text(encoding="utf-8")
        self.script = (self.root / "static/custom/js/nodo-tooltips.js").read_text(encoding="utf-8")
        self.styles = (self.root / "static/custom/css/nodo-tooltips.css").read_text(encoding="utf-8")

    def test_global_assets_are_loaded_by_backoffice_base(self):
        self.assertIn("custom/css/nodo-tooltips.css", self.base)
        self.assertIn("custom/js/nodo-tooltips.js", self.base)

    def test_tooltip_exposes_accessible_relationship(self):
        self.assertIn('setAttribute("role", "tooltip")', self.script)
        self.assertIn('setAttribute("aria-describedby"', self.script)
        self.assertIn('getAttribute("aria-label")', self.script)

    def test_keyboard_and_reduced_motion_are_supported(self):
        self.assertIn('event.key === "Escape"', self.script)
        self.assertIn('"focusin"', self.script)
        self.assertIn("prefers-reduced-motion: reduce", self.styles)

    def test_common_icon_actions_receive_accessible_names(self):
        for icon in ("fa-edit", "fa-trash", "fa-eye", "fa-download"):
            with self.subTest(icon=icon):
                self.assertIn(f'"{icon}"', self.script)
