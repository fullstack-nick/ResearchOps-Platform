from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from app.auth.entra import EntraConfigurationError, validate_entra_token
from app.core.config import Settings
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient


async def test_auth_me_returns_default_demo_user(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "demo.researchops@example.test"
    assert "operations_admin" in body["roles"]
    assert body["research_group"] == "operations"
    assert body["is_active"] is True


async def test_auth_me_with_dev_user_header(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/me", headers={"X-Dev-User-Email": "researcher.alice@example.test"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "researcher.alice@example.test"
    assert body["roles"] == ["researcher"]
    assert body["research_group"] == "genomics"


async def test_auth_me_unknown_user_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/me", headers={"X-Dev-User-Email": "nobody@example.test"}
    )

    assert response.status_code == 401


async def test_auth_config_reports_dev_mode(client: AsyncClient) -> None:
    response = await client.get("/api/auth/config")

    assert response.status_code == 200
    body = response.json()
    assert body["auth_mode"] == "development"
    assert body["entra_client_id"] is None


async def test_auth_dev_users_lists_seeded_personas(client: AsyncClient) -> None:
    response = await client.get("/api/auth/dev-users")

    assert response.status_code == 200
    emails = {entry["email"] for entry in response.json()["users"]}
    assert {
        "demo.researchops@example.test",
        "researcher.alice@example.test",
        "lead.bob@example.test",
        "finance.carol@example.test",
        "hr.dan@example.test",
        "it.eve@example.test",
        "admin.frank@example.test",
    } <= emails


def _make_entra_settings() -> Settings:
    return Settings(
        auth_mode="entra",
        entra_tenant_id="00000000-0000-0000-0000-000000000000",
        entra_client_id="00000000-0000-0000-0000-000000000111",
        entra_audience="00000000-0000-0000-0000-000000000111",
        entra_required_scope="access_as_user",
    )


def _sign_test_jwt(private_key: rsa.RSAPrivateKey, payload: dict[str, Any]) -> str:
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_validate_entra_token_accepts_a_correctly_signed_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    settings = _make_entra_settings()
    now = datetime.now(UTC)
    payload = {
        "oid": "user-oid-1",
        "preferred_username": "alice@example.com",
        "name": "Alice Researcher",
        "aud": settings.entra_audience,
        "iss": settings.entra_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "scp": "access_as_user openid profile",
        "roles": ["researcher"],
    }
    token = _sign_test_jwt(private_key, payload)

    class FakeSigningKey:
        def __init__(self, key: Any) -> None:
            self.key = key

    class FakeJwksClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def get_signing_key_from_jwt(self, _token: str) -> FakeSigningKey:
            return FakeSigningKey(public_key)

    monkeypatch.setattr("app.auth.entra.PyJWKClient", FakeJwksClient)

    claims = validate_entra_token(settings, token)
    assert claims["oid"] == "user-oid-1"
    assert claims["preferred_username"] == "alice@example.com"


def test_validate_entra_token_requires_settings() -> None:
    settings = Settings(auth_mode="entra")

    with pytest.raises(EntraConfigurationError):
        validate_entra_token(settings, "irrelevant-token")
