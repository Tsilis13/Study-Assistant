"""
One shared rate limiter for the whole app (main.py plugs it in: app.state.limiter = limiter).

Logged-in users are limited per ACCOUNT, everyone else per IP address. The token is really
verified, so nobody can pick someone else's bucket with a fake token.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import security


def user_or_ip_key(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        user_id = security.decode_access_token(token)
        if user_id is not None:
            return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=user_or_ip_key)
