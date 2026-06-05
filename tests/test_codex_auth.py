import base64
import json

from auto_auth_cli.tools.codex.auth import extract_metadata


def jwt_for(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}."


def test_extract_metadata_uses_email_account_id_and_plan_from_codex_tokens():
    auth = {
        "auth_mode": "chatgpt",
        "tokens": {
            "id_token": jwt_for(
                {
                    "email": "Minh+Codex@example.com",
                    "https://api.openai.com/auth": {
                        "chatgpt_account_id": "account-123",
                        "chatgpt_plan_type": "pro",
                    },
                }
            ),
            "access_token": jwt_for({"email": "other@example.com"}),
            "refresh_token": "secret-refresh",
        },
    }

    metadata = extract_metadata(auth)

    assert metadata.email == "Minh+Codex@example.com"
    assert metadata.account_id == "account-123"
    assert metadata.plan_type == "pro"
    assert metadata.label == "Minh+Codex@example.com"
    assert metadata.key == "minh_codex_example_com"
