# Chemin exact : tests/test_gas_client.py [NEW]
import asyncio
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from scraper.gas_client import GasWebAppClient


class TestGasWebAppClient(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GasWebAppClient(
            web_app_url="https://script.example/exec",
            api_secret="test-api-secret",
            hmac_secret="test-hmac-secret",
            timeout_seconds=1.0,
        )

    @patch("scraper.gas_client.aiohttp.ClientSession")
    def test_write_test_posts_expected_payload(
        self,
        mock_session_factory: MagicMock,
    ) -> None:
        session = MagicMock()
        session.__aenter__.return_value = session
        get_context = MagicMock()
        get_response = AsyncMock()
        get_response.status = 200
        get_response.json = AsyncMock(return_value={"status": "success", "keys": ["existing-id"]})
        get_context.__aenter__ = AsyncMock(return_value=get_response)
        get_context.__aexit__ = AsyncMock(return_value=False)
        post_context = MagicMock()
        post_response = AsyncMock()
        post_response.status = 200
        post_response.json = AsyncMock(return_value={"status": "success", "message": "ok"})
        post_context.__aenter__ = AsyncMock(return_value=post_response)
        post_context.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = get_context
        session.post.return_value = post_context
        mock_session_factory.return_value = session

        result = asyncio.run(self.client.execute_write_test())
        self.assertEqual(result["status"], "success")
        session.get.assert_called_once_with(
            "https://script.example/exec",
            params={"action": "get_config", "secret": "test-api-secret"},
        )
        session.post.assert_called_once()
        self.assertEqual([call[0] for call in session.method_calls], ["get", "post"])
        args, kwargs = session.post.call_args
        self.assertEqual(args, ("https://script.example/exec",))
        payload = json.loads(kwargs["data"])
        self.assertEqual(
            payload,
            {
                "offers": [
                    [
                        "29/09/2026",
                        "ToyTest yaya",
                        9999,
                        99999,
                        0,
                        "MaVille",
                        999,
                        "NC",
                        "CONFORME",
                        "AlerteRisque",
                        "Commentaire",
                        "TESTAUTO",
                        "SOURCETEST",
                        "https://www.testsite.fr/ad/voitures/3206865999",
                    ],
                    [
                        "29/09/2026",
                        "ToyTest yaya",
                        9999,
                        99999,
                        0,
                        "MaVille",
                        999,
                        "NC",
                        "NON CONFORME",
                        "AlerteRisque",
                        "Commentaire",
                        "TESTAUTO",
                        "SOURCETEST",
                        "https://www.testsite.fr/ad/voitures/3206865999?test=non-conforme",
                    ]
                ],
                "log": {
                    "total_count": 2
                },
                "timestamp": payload["timestamp"],
                "request_id": payload["request_id"],
            },
        )
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(set(kwargs["params"]), {"signature"})
        self.assertRegex(kwargs["params"]["signature"], r"^[a-f0-9]{64}$")
        expected_signature = hmac.new(
            b"test-hmac-secret",
            kwargs["data"],
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(kwargs["params"]["signature"], expected_signature)
        self.assertLessEqual(abs(int(time.time()) - payload["timestamp"]), 5)
        self.assertRegex(payload["request_id"], r"^[a-f0-9-]{36}$")

    @patch("scraper.gas_client.aiohttp.ClientSession")
    def test_write_test_rejects_application_error(self, mock_session_factory: MagicMock) -> None:
        session = MagicMock()
        session.__aenter__.return_value = session
        get_context = MagicMock()
        get_response = AsyncMock()
        get_response.status = 200
        get_response.json = AsyncMock(return_value={"status": "success", "keys": []})
        get_context.__aenter__ = AsyncMock(return_value=get_response)
        get_context.__aexit__ = AsyncMock(return_value=False)
        post_context = MagicMock()
        post_response = AsyncMock()
        post_response.status = 200
        post_response.json = AsyncMock(return_value={"status": "error", "message": "denied"})
        post_context.__aenter__ = AsyncMock(return_value=post_response)
        post_context.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = get_context
        session.post.return_value = post_context
        mock_session_factory.return_value = session

        with self.assertRaisesRegex(RuntimeError, "GAS rejected"):
            asyncio.run(self.client.execute_write_test())

        session.post.assert_called_once()

    @patch("scraper.gas_client.aiohttp.ClientSession")
    def test_write_test_does_not_duplicate_sample_url(self, mock_session_factory: MagicMock) -> None:
        session = MagicMock()
        session.__aenter__.return_value = session
        response_context = MagicMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={
            "status": "success",
            "keys": ["https://www.testsite.fr/ad/voitures/3206865999"],
        })
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = response_context
        mock_session_factory.return_value = session

        with self.assertRaisesRegex(RuntimeError, "already exist"):
            asyncio.run(self.client.execute_write_test())

        session.post.assert_not_called()

    @patch("scraper.gas_client.aiohttp.ClientSession")
    def test_write_test_rejects_if_either_sample_url_exists(self, mock_session_factory: MagicMock) -> None:
        session = MagicMock()
        session.__aenter__.return_value = session
        response_context = MagicMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={
            "status": "success",
            "keys": ["https://www.testsite.fr/ad/voitures/3206865999?test=non-conforme"],
        })
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = response_context
        mock_session_factory.return_value = session

        with self.assertRaisesRegex(RuntimeError, "already exist"):
            asyncio.run(self.client.execute_write_test())

        session.post.assert_not_called()

    @patch("scraper.gas_client.aiohttp.ClientSession")
    def test_fetch_keys_rejects_invalid_keys(self, mock_session_factory: MagicMock) -> None:
        session = MagicMock()
        session.__aenter__.return_value = session
        response_context = MagicMock()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={"status": "success", "keys": [123]})
        response_context.__aenter__ = AsyncMock(return_value=response)
        response_context.__aexit__ = AsyncMock(return_value=False)
        session.get.return_value = response_context
        mock_session_factory.return_value = session

        with self.assertRaisesRegex(RuntimeError, "invalid keys list"):
            asyncio.run(self.client.fetch_keys())


if __name__ == "__main__":
    unittest.main()