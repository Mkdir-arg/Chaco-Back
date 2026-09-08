import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ModernModalStylesTests(SimpleTestCase):
    def test_modal_responsive_respeta_el_estado_hidden_del_overlay(self):
        css = Path(settings.BASE_DIR, "static", "custom", "css", "responsive.css").read_text(encoding="utf-8")

        self.assertIn(".modal-responsive.hidden", css)
        self.assertIn(".modal-responsive.hidden {\n    display: none;", css)


class MobileSidebarTemplateTests(SimpleTestCase):
    def test_close_control_is_hidden_while_mobile_sidebar_is_closed(self):
        template = Path(settings.BASE_DIR, "templates", "includes", "sidebar", "base.html").read_text(encoding="utf-8")

        close_control = re.search(
            r'<div[^>]*class="absolute left-full top-0[^>]*>(?P<content>.*?)</div>',
            template,
            flags=re.DOTALL,
        )

        self.assertIsNotNone(close_control)
        self.assertIn('x-show="sidebarOpen"', close_control.group(0))
        self.assertIn('aria-label="Cerrar sidebar"', close_control.group("content"))

    def test_brand_header_does_not_close_the_sidebar_early(self):
        template = Path(settings.BASE_DIR, "templates", "includes", "sidebar", "base.html").read_text(encoding="utf-8")

        self.assertNotIn(
            "</template>\n        </div>\n\n        </div>\n    </div>\n\n    <!-- ── Navegación compartida",
            template,
        )
