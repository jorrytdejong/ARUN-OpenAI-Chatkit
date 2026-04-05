"""Auth0 access-token verification helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, decode
from jwt.exceptions import InvalidTokenError

from .config import Settings


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthenticatedUser:
    sub: str
    email: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


class Auth0TokenVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jwks_client = PyJWKClient(
            f"{settings.auth0_issuer}.well-known/jwks.json"
        )

    def verify(self, token: str) -> AuthenticatedUser:
        if not self._settings.vite_auth0_domain or not self._settings.vite_auth0_audience:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth0 API is not configured.",
            )

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.vite_auth0_audience,
                issuer=self._settings.auth0_issuer,
            )
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token.",
            ) from exc

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token is missing a subject claim.",
            )

        email = claims.get("email")
        return AuthenticatedUser(
            sub=subject,
            email=email if isinstance(email, str) else None,
            claims=claims,
        )


def get_token_verifier(request: Request) -> Auth0TokenVerifier:
    return request.app.state.token_verifier


async def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: Auth0TokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    return verifier.verify(credentials.credentials)
