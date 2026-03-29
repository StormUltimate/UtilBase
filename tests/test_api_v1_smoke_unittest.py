import unittest

from app import create_app


class ApiV1SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def _login_admin(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        self.assertEqual(resp.status_code, 200, msg=f"login failed: {resp.get_json()}")
        data = resp.get_json() or {}
        token = data.get("access_token")
        self.assertTrue(token, "access_token missing")
        return {"Authorization": f"Bearer {token}"}

    def test_auth_me(self):
        headers = self._login_admin()
        resp = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(resp.status_code, 200, msg=resp.get_json())
        data = resp.get_json() or {}
        self.assertIn("id", data)
        self.assertIn("role", data)

    def test_requests_list_and_summary(self):
        headers = self._login_admin()
        r1 = self.client.get("/api/v1/requests?limit=5", headers=headers)
        self.assertEqual(r1.status_code, 200, msg=r1.get_json())
        body = r1.get_json() or {}
        self.assertIn("items", body)
        self.assertIn("total", body)

        r2 = self.client.get("/api/v1/requests/summary", headers=headers)
        self.assertEqual(r2.status_code, 200, msg=r2.get_json())
        summary = r2.get_json() or {}
        self.assertIn("by_status", summary)


if __name__ == "__main__":
    unittest.main()
