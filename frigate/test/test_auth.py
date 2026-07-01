import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frigate.api.auth import (
    get_login_request_location,
    notified_login_tokens,
    send_login_success_telegram_message_once,
    send_login_success_telegram_message,
)
from frigate.config.auth import AuthConfig, LoginTelegramConfig


def create_telegram_response():
    response = MagicMock()
    response.__enter__.return_value.status = 200
    response.__enter__.return_value.read.return_value = b'{"ok": true}'
    return response


def create_request(
    login_telegram_config: LoginTelegramConfig,
    forwarded_for: str = "203.0.113.10, 10.0.0.1",
):
    return SimpleNamespace(
        app=SimpleNamespace(
            frigate_config=SimpleNamespace(
                auth=SimpleNamespace(login_telegram=login_telegram_config)
            )
        ),
        headers={"x-forwarded-for": forwarded_for},
        client=SimpleNamespace(host="198.51.100.20"),
    )


class TestAuthLoginTelegram(unittest.TestCase):
    def test_auth_login_telegram_config_defaults_to_disabled(self):
        auth_config = AuthConfig()

        assert not auth_config.login_telegram.enabled
        assert auth_config.login_telegram.bot_token is None
        assert auth_config.login_telegram.chat_id is None
        assert auth_config.login_telegram.parse_mode == "HTML"
        assert not auth_config.login_telegram.include_location
        assert auth_config.login_telegram.location_api_url == (
            "https://ipapi.co/{ip}/json/"
        )
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

        response = create_telegram_response()

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

        response = create_telegram_response()

        with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = response

            send_login_success_telegram_message(request, "admin<root>")

        telegram_request = mock_urlopen.call_args.args[0]
        payload = json.loads(telegram_request.data.decode("utf-8"))
        assert "User: admin&lt;root&gt;" in payload["text"]

    def test_get_login_request_location_formats_location(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = json.dumps(
            {
                "city": "Mountain View",
                "region": "California",
                "country_name": "United States",
                "latitude": 37.422,
                "longitude": -122.084,
            }
        ).encode("utf-8")

        with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = response

            location = get_login_request_location(
                "8.8.8.8", "https://ipapi.co/{ip}/json/", 10
            )

        assert location == "Mountain View, California, United States (37.422, -122.084)"
        location_request = mock_urlopen.call_args.args[0]
        assert location_request.full_url == "https://ipapi.co/8.8.8.8/json/"

    def test_get_login_request_location_skips_private_ip(self):
        with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
            location = get_login_request_location(
                "192.168.1.10", "https://ipapi.co/{ip}/json/", 10
            )

        assert location is None
        mock_urlopen.assert_not_called()

    def test_send_login_success_telegram_message_includes_location(self):
        request = create_request(
            LoginTelegramConfig(
                enabled=True,
                bot_token="123456:telegram-token",
                chat_id="987654321",
                include_location=True,
            ),
            forwarded_for="8.8.8.8, 10.0.0.1",
        )

        location_response = MagicMock()
        location_response.__enter__.return_value.status = 200
        location_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "city": "Mountain View",
                "region": "California",
                "country_name": "United States",
            }
        ).encode("utf-8")
        telegram_response = create_telegram_response()

        with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [location_response, telegram_response]

            send_login_success_telegram_message(request, "admin")

        assert mock_urlopen.call_count == 2
        telegram_request = mock_urlopen.call_args_list[1].args[0]
        payload = json.loads(telegram_request.data.decode("utf-8"))
        assert "IP address: 8.8.8.8" in payload["text"]
        assert "Location: Mountain View, California, United States" in payload["text"]

    def test_send_login_success_telegram_message_once_sends_once_per_token(self):
        notified_login_tokens.clear()
        request = create_request(
            LoginTelegramConfig(
                enabled=True,
                bot_token="123456:telegram-token",
                chat_id="987654321",
            )
        )

        response = create_telegram_response()

        with patch("frigate.api.auth.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = response

            send_login_success_telegram_message_once(
                request, "admin", "encoded-token", 9999999999
            )
            send_login_success_telegram_message_once(
                request, "admin", "encoded-token", 9999999999
            )

        mock_urlopen.assert_called_once()
        notified_login_tokens.clear()


if __name__ == "__main__":
    unittest.main()
