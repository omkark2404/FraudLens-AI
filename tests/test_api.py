import unittest
from unittest.mock import patch
from core.app_factory import create_app
from core.config import config
import io
import json

class TestAPI(unittest.TestCase):
    def setUp(self):
        # Create app and client
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        # Set a dummy API key for testing
        self.original_api_key = config.API_KEY
        config.API_KEY = "test-api-key"

    def tearDown(self):
        config.API_KEY = self.original_api_key

    def test_unauthorized_access(self):
        # Without API key
        resp = self.client.post("/api/v1/upload")
        self.assertEqual(resp.status_code, 401)
        
        # With wrong API key
        resp = self.client.post(
            "/api/v1/upload",
            headers={"X-API-Key": "wrong-key"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_submit_job_missing_files(self):
        resp = self.client.post(
            "/api/v1/upload",
            headers={"X-API-Key": "test-api-key"}
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("at least one of license_file or insurance_file is required", resp.get_json()["error"])

    @patch("core.security.is_safe_file")
    @patch("services.job_service.submit_job")
    def test_submit_job_success(self, mock_submit, mock_is_safe):
        # Setup mocks
        mock_is_safe.return_value = True
        
        def fake_submit(job_id, dl_path, ic_path):
            pass # DO NOT actually spawn threads
        mock_submit.side_effect = fake_submit

        data = {
            "license_file": (io.BytesIO(b"fake image data"), "license.png")
        }

        resp = self.client.post(
            "/api/v1/upload",
            headers={"X-API-Key": "test-api-key"},
            data=data,
            content_type="multipart/form-data"
        )
        
        self.assertEqual(resp.status_code, 202)
        json_data = resp.get_json()
        self.assertIn("job_id", json_data)
        self.assertEqual(json_data["status"], "pending")

    @patch("routes.api_routes.get_job")
    def test_get_job_status(self, mock_get_job):
        mock_get_job.return_value = {
            "job_id": "job-123",
            "status": "done",
            "result_json": json.dumps({"test": "data"})
        }

        resp = self.client.get(
            "/api/v1/result/job-123",
            headers={"X-API-Key": "test-api-key"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "done")

    @patch("routes.api_routes.get_job")
    def test_get_job_status_not_found(self, mock_get_job):
        mock_get_job.return_value = None

        resp = self.client.get(
            "/api/v1/result/job-999",
            headers={"X-API-Key": "test-api-key"}
        )
        self.assertEqual(resp.status_code, 404)

if __name__ == "__main__":
    unittest.main()
