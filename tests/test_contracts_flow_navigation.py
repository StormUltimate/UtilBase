import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContractsFlowNavigationTests(unittest.TestCase):
    def _read(self, rel_path: str) -> str:
        return (ROOT / rel_path).read_text(encoding="utf-8")

    def test_contract_list_links_to_view_with_next(self):
        text = self._read("app/templates/contracts/list.html")
        self.assertIn(
            "url_for('contracts.view_contract', contract_id=row.contract.id, next=request.full_path)",
            text,
        )

    def test_contract_view_has_back_url(self):
        text = self._read("app/templates/contracts/view.html")
        self.assertIn("back_url or url_for('contracts.list_contracts')", text)

    def test_contract_view_has_wizard_link_and_scope_label(self):
        text = self._read("app/templates/contracts/view.html")
        self.assertIn("url_for('contracts.edit_contract_wizard', contract_id=contract.id)", text)
        self.assertIn("Перечень оборудования", text)
        self.assertNotIn('id="tab-equipment"', text)

    def test_contract_route_passes_back_url(self):
        text = self._read("app/blueprints/contracts/routes.py")
        self.assertIn('back_url = _safe_next_url(url_for("contracts.list_contracts"))', text)
        self.assertIn("back_url=back_url", text)

    def test_contract_edit_route_redirects_to_wizard(self):
        text = self._read("app/blueprints/contracts/routes.py")
        self.assertIn("def edit_contract(contract_id):", text)
        self.assertIn('url_for("contracts.edit_contract_wizard", contract_id=contract_id)', text)


if __name__ == "__main__":
    unittest.main()
