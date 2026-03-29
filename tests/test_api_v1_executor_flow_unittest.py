import os
import unittest

from app import create_app


@unittest.skipUnless(
    os.getenv("RUN_API_V1_E2E", "").lower() in ("1", "true", "yes"),
    "Set RUN_API_V1_E2E=true to run integration flow against configured DB",
)
class ApiV1ExecutorFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.username = os.getenv("API_E2E_USERNAME", "admin")
        cls.password = os.getenv("API_E2E_PASSWORD", "admin")

    def _login(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": self.username, "password": self.password},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.get_json())
        token = (resp.get_json() or {}).get("access_token")
        self.assertTrue(token, "Missing access_token")
        return {"Authorization": f"Bearer {token}"}

    def _pick_request_id(self, headers):
        resp = self.client.get("/api/v1/requests?limit=1", headers=headers)
        self.assertEqual(resp.status_code, 200, msg=resp.get_json())
        items = (resp.get_json() or {}).get("items") or []
        if not items:
            self.skipTest("No requests available for e2e flow")
        return items[0]["id"]

    def test_executor_flow_endpoints_accessible(self):
        headers = self._login()
        request_id = self._pick_request_id(headers)

        # 1) detail
        detail = self.client.get(f"/api/v1/requests/{request_id}", headers=headers)
        self.assertEqual(detail.status_code, 200, msg=detail.get_json())

        # 2) checklist template
        tmpl = self.client.get(
            f"/api/v1/requests/{request_id}/checklist-template",
            headers=headers,
        )
        self.assertEqual(tmpl.status_code, 200, msg=tmpl.get_json())

        # 3) items/payments/chat (read)
        items = self.client.get(f"/api/v1/requests/{request_id}/items", headers=headers)
        self.assertEqual(items.status_code, 200, msg=items.get_json())

        payments = self.client.get(
            f"/api/v1/requests/{request_id}/payments",
            headers=headers,
        )
        self.assertEqual(payments.status_code, 200, msg=payments.get_json())

        chat = self.client.get(
            f"/api/v1/requests/{request_id}/chat/messages",
            headers=headers,
        )
        self.assertEqual(chat.status_code, 200, msg=chat.get_json())

        logs = self.client.get(f"/api/v1/requests/{request_id}/logs", headers=headers)
        self.assertEqual(logs.status_code, 200, msg=logs.get_json())


if __name__ == "__main__":
    unittest.main()
