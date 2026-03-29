import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NavigationConventionsTests(unittest.TestCase):
    def _read(self, rel_path: str) -> str:
        return (ROOT / rel_path).read_text(encoding="utf-8")

    def test_equipment_templates_have_no_path_artifacts(self):
        eq_templates = ROOT / "app" / "templates" / "equipment"
        for file_path in eq_templates.glob("*.html"):
            text = file_path.read_text(encoding="utf-8")
            self.assertNotRegex(
                text,
                r"^\s*<!--\s*#?\s*Path:",
                msg=f"Found path artifact in {file_path}",
            )

    def test_client_detail_url_uses_client_id_param(self):
        templates_root = ROOT / "app" / "templates"
        pattern = re.compile(r"url_for\('clients\.client_detail',\s*id=")
        offenders = []
        for file_path in templates_root.rglob("*.html"):
            text = file_path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(file_path))
        self.assertFalse(offenders, msg=f"Wrong client_detail param in: {offenders}")

    def test_key_edit_links_pass_next_param(self):
        checks = [
            ("app/templates/clients/detail.html", r"url_for\('equipment\.edit_equipment'.*next="),
            ("app/templates/equipment/list.html", r"url_for\('equipment\.edit_equipment'.*next="),
            ("app/templates/clients/detail.html", r"url_for\('requests\.view_request'.*next="),
            ("app/templates/clients/detail.html", r"url_for\('contracts\.view_contract'.*next="),
            ("app/templates/requests/view.html", r"url_for\('requests\.edit_request'.*next="),
            ("app/templates/requests/view.html", r"url_for\('contracts\.view_contract'.*next="),
            ("app/templates/requests/list.html", r"url_for\('requests\.edit_request'.*next="),
            ("app/templates/requests/list.html", r"url_for\('requests\.view_request'.*next="),
            ("app/templates/requests/today.html", r"url_for\('requests\.view_request'.*next="),
            ("app/templates/search.html", r"url_for\('requests\.view_request'.*next="),
            ("app/templates/contracts/list.html", r"url_for\('contracts\.view_contract'.*next="),
            ("app/templates/contracts/view.html", r"url_for\('contracts\.edit_contract'.*next="),
            ("app/templates/admin/index.html", r"url_for\('users\.edit_user'.*next="),
            ("app/templates/admin/index.html", r"url_for\('workers\.edit_worker'.*next="),
            ("app/templates/clients/detail.html", r"url_for\('photos\.edit_photo'.*next="),
            ("app/templates/photos/photos.html", r"url_for\('photos\.upload_photo'.*next="),
            ("app/templates/photos/photos.html", r"url_for\('photos\.import_chat'.*next="),
        ]
        for rel_path, regex in checks:
            text = self._read(rel_path)
            self.assertRegex(text, regex, msg=f"Missing next in {rel_path}")


if __name__ == "__main__":
    unittest.main()
