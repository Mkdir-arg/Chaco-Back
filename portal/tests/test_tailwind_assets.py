from django.test import TestCase
from django.urls import reverse


class PortalTailwindAssetTests(TestCase):
    def test_portal_usa_el_css_compilado_en_lugar_del_cdn(self):
        response = self.client.get(reverse("portal:home"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("/static/custom/css/tailwind.css", html)
        self.assertNotIn("cdn.tailwindcss.com", html)
