"""auth middleware logic"""
import jwt
from starlette.authentication import (AuthCredentials, AuthenticationBackend,
                                      AuthenticationError, BaseUser)
from starlette.responses import JSONResponse
from tortoise.exceptions import DoesNotExist

from .models import User
from .settings import JWT_SECRET_KEY


class JWTUser(BaseUser):
    """Authenticated User object"""

    def __init__(self, user_id, username: str):
        self.user_id = user_id
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username


class JWTAuthBackend(AuthenticationBackend):
    """Authenicate against given JWT"""
    async def authenticate(self, conn):
        if "Authorization" not in conn.headers:
            return

        auth = conn.headers["Authorization"]
        scheme, token = auth.split()

        if scheme.lower() != 'bearer':
            return

        try:
            payload = jwt.decode(token, key=str(
                JWT_SECRET_KEY), algorithm='HS256')
        except jwt.InvalidTokenError as error:
            raise AuthenticationError(str(error))

        try:
            user = await User.get(id=payload['id'])
        except DoesNotExist:
            raise AuthenticationError('Invalid User, log in with a valid user')

        # if token id is not what is in the database token is invalid
        if payload['token_id'] != user.token_id.hex:
            raise AuthenticationError('Please log in again')

        return AuthCredentials(["authenticated"]), JWTUser(user.id, user.username)


def on_auth_error(_request, error: Exception):
    """returns a json reponse with error message"""
    return JSONResponse({"error": str(error)}, status_code=401)
