import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frigate.api.auth import send_login_success_telegram_message
from frigate.config.auth import AuthConfig, LoginTelegramConfig


def create_request(login_telegram_config: LoginTelegramConfig):
	return SimpleNamespace(
		app=SimpleNamespace(
			frigate_config=SimpleNamespace(
				auth=SimpleNamespace(login_telegram=login_telegram_config)
			)
		),
		headers={"x-forwarded-for": "203.0.113.10, 10.0.0.1"},
		client=SimpleNamespace(host="198.51.100.20"),
	)


class TestAuthLoginTelegram(unittest.TestCase):
	def test_auth_login_telegram_config_defaults_to_disabled(self):
		auth_config = AuthConfig()

		assert not auth_config.login_telegram.enabled
		assert auth_config.login_telegram.bot_token is None
		assert auth_config.login_telegram.chat_id is None
		assert auth_config.login_telegram.parse_mode == "HTML"
		assert auth_config.login_telegram.timeout == 10

	def test_send_login_success_telegram_message_skips_when_disabled(self):
		request = create_request(LoginTelegramConfig(enabled=False))

		with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
			send_login_success_telegram_message(request, "admin")

		mock_urlopen.assert_not_called()

	def test_send_login_success_telegram_message_skips_when_missing_config(self):
		request = create_request(LoginTelegramConfig(enabled=True))

		with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
			send_login_success_telegram_message(request, "admin")

		mock_urlopen.assert_not_called()

	def test_send_login_success_telegram_message_posts_payload(self):
		request = create_request(
			LoginTelegramConfig(
				enabled=True,
				bot_token="123456:telegram-token",
				chat_id="987654321",
			)
		)

		response = MagicMock()
		response.__enter__.return_value.status = 200

		with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
			mock_urlopen.return_value = response

			send_login_success_telegram_message(request, "admin")

		mock_urlopen.assert_called_once()
		telegram_request = mock_urlopen.call_args.args[0]
		assert telegram_request.full_url == (
			"https://api.telegram.org/bot123456:telegram-token/sendMessage"
		)
		assert mock_urlopen.call_args.kwargs["timeout"] == 10

		payload = json.loads(telegram_request.data.decode("utf-8"))
		assert payload["chat_id"] == "987654321"
		assert payload["parse_mode"] == "HTML"
		assert payload["disable_web_page_preview"]
		assert "Frigate login succeeded" in payload["text"]
		assert "User: admin" in payload["text"]
		assert "IP address: 203.0.113.10" in payload["text"]

	def test_send_login_success_telegram_message_escapes_html(self):
		request = create_request(
			LoginTelegramConfig(
				enabled=True,
				bot_token="123456:telegram-token",
				chat_id="987654321",
			)
		)

		response = MagicMock()
		response.__enter__.return_value.status = 200

		with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
			mock_urlopen.return_value = response

			send_login_success_telegram_message(request, "admin<root>")

		telegram_request = mock_urlopen.call_args.args[0]
		payload = json.loads(telegram_request.data.decode("utf-8"))
		assert "User: admin&lt;root&gt;" in payload["text"]


if __name__ == "__main__":
	unittest.main()

