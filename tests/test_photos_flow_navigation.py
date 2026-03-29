import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PhotosFlowNavigationTests(unittest.TestCase):
    def _read(self, rel_path: str) -> str:
        return (ROOT / rel_path).read_text(encoding="utf-8")

    def test_photos_edit_template_shows_back_when_next(self):
        text = self._read("app/templates/photos/edit.html")
        self.assertIn("{% if next_url %}", text)
        self.assertIn('href="{{ next_url }}"', text)
        self.assertIn('<i class="bi bi-arrow-left"></i> Назад', text)

    def test_photos_edit_route_uses_safe_next(self):
        text = self._read("app/blueprints/photos/routes.py")
        self.assertIn("def _safe_relative_next():", text)
        self.assertIn("next_url = _safe_relative_next()", text)
        self.assertIn("dest = _safe_relative_next()", text)

    def test_photos_list_actions_pass_next(self):
        text = self._read("app/templates/photos/photos.html")
        self.assertIn("url_for('photos.upload_photo', next=request.full_path)", text)
        self.assertIn("url_for('photos.import_chat', next=request.full_path)", text)

    def test_import_chat_respects_next(self):
        route_text = self._read("app/blueprints/photos/routes.py")
        tpl_text = self._read("app/templates/photos/import_chat.html")
        self.assertIn("next_url = _safe_relative_next()", route_text)
        self.assertIn(
            "return render_template('photos/import_chat.html', next_url=next_url)", route_text
        )
        self.assertIn("next_url or url_for('photos.photos_list')", tpl_text)


if __name__ == "__main__":
    unittest.main()
