"""Validation JWT (JWKS Keycloak) et contrôle d'accès par rôles (RBAC)."""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from .audit import write_audit
from .config import settings

bearer_scheme = HTTPBearer(auto_error=False)
# Les clés publiques sont mises en cache ; PyJWKClient re-télécharge si un `kid` inconnu apparaît
_jwks = PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=3600)


@dataclass(frozen=True)
class User:
    sub: str
    username: str
    email: str | None
    roles: list[str]
    azp: str | None

    def identity(self) -> dict:
        return {"sub": self.sub, "username": self.username, "email": self.email, "roles": self.roles}


def client_ctx(request: Request) -> dict:
    return {
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "client_app": request.headers.get("x-client-app"),
        "method": request.method,
        "path": request.url.path,
    }


def _reject(request: Request, reason: str, code: int = 401):
    write_audit({"event": "AUTH_FAILED", "reason": reason, **client_ctx(request)})
    raise HTTPException(
        status_code=code,
        detail=f"Authentification refusée : {reason}",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if creds is None:
        _reject(request, "jeton Bearer manquant")

    token = creds.credentials
    try:
        signing_key = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],          # liste blanche : bloque alg=none / HS256
            issuer=settings.issuer,
            options={"require": ["exp", "iat", "iss", "sub"], "verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        _reject(request, "jeton expiré")
    except PyJWKClientConnectionError:
        write_audit({"event": "JWKS_UNREACHABLE", **client_ctx(request)})
        raise HTTPException(503, "Serveur d'identité injoignable")
    except (jwt.InvalidTokenError, jwt.PyJWKClientError):
        _reject(request, "jeton invalide")

    # Le jeton doit avoir été émis pour notre client (pas un autre client du realm)
    if claims.get("azp") != settings.keycloak_client_id:
        _reject(request, "jeton émis pour un autre client")

    return User(
        sub=claims["sub"],
        username=claims.get("preferred_username", ""),
        email=claims.get("email"),
        roles=claims.get("realm_access", {}).get("roles", []),
        azp=claims.get("azp"),
    )


def require_roles(*allowed: str):
    def dependency(request: Request, user: User = Depends(get_current_user)) -> User:
        if not set(allowed) & set(user.roles):
            write_audit({
                "event": "ACCESS_DENIED",
                "required_roles": list(allowed),
                "user": user.identity(),
                **client_ctx(request),
            })
            raise HTTPException(status_code=403, detail="Rôle insuffisant pour cette ressource")
        return user

    return dependency