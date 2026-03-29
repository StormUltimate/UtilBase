import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClientFlowNavigationTests(unittest.TestCase):
    def _read(self, rel_path: str) -> str:
        return (ROOT / rel_path).read_text(encoding="utf-8")

    def test_client_detail_equipment_edit_has_next(self):
        text = self._read("app/templates/clients/detail.html")
        self.assertIn(
            "url_for('equipment.edit_equipment', id=eq.id, next=url_for('clients.client_detail', client_id=client.id, tab='equipment'))",
            text,
        )

    def test_client_detail_request_view_has_next(self):
        text = self._read("app/templates/clients/detail.html")
        self.assertIn("url_for('requests.view_request', id=req.id, next=request.full_path)", text)

    def test_request_view_uses_back_url(self):
        text = self._read("app/templates/requests/view.html")
        self.assertIn("back_url or url_for('requests.list_requests')", text)
        self.assertIn("back_url or url_for('requests.calendar')", text)

    def test_request_view_route_passes_back_url(self):
        text = self._read("app/blueprints/requests/routes.py")
        self.assertIn("back_url = _safe_next_url(default_back)", text)
        self.assertIn(
            "render_template('requests/view.html', req=req, from_calendar=from_calendar, back_url=back_url)",
            text,
        )

    def test_equipment_edit_uses_next_url(self):
        route_text = self._read("app/blueprints/equipment/routes.py")
        tpl_text = self._read("app/templates/equipment/edit.html")
        self.assertIn("next_url = _safe_next_url(default_back)", route_text)
        self.assertIn("return redirect(next_url)", route_text)
        self.assertIn('name="next" value="{{ next_url or \'\' }}"', tpl_text)
        self.assertIn("next_url or url_for('equipment.list_equipment')", tpl_text)


if __name__ == "__main__":
    unittest.main()
