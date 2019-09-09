"""app and graphql resolver set up in this module"""
import asyncio
import base64
import hashlib
import os
import uuid

import bcrypt
import jwt
from ariadne import (ObjectType, SubscriptionType,
                     convert_kwargs_to_snake_case, load_schema_from_path)
from ariadne.asgi import GraphQL
from ariadne.contrib.tracing.apollotracing import ApolloTracingExtension
from ariadne.executable_schema import make_executable_schema
from graphql.pyutils import EventEmitter, EventEmitterAsyncIterator
from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from tortoise.exceptions import DoesNotExist

from .auth import JWTAuthBackend, JWTUser, on_auth_error
from .models import Post, User, close_connections, init_db
from .settings import DEBUG, JWT_SECRET_KEY

APP = Starlette()

SCHEMA = load_schema_from_path(os.path.join("example_site", "schema.graphql"))

MUTATION = ObjectType("Mutation")
PUBSUB = EventEmitter()
QUERY = ObjectType("Query")
POST = ObjectType("Post")
SUBSCRIPTION = SubscriptionType()


@QUERY.field("users")
async def get_all_users(_root, _info):
    """return list of all users"""
    results = await User.all()
    return results


@QUERY.field("posts")
async def get_all_posts(_root, _info):
    """return a list of all posts"""
    results = await Post.all()
    return results


@POST.field("user")
async def get_post_user(post: Post, _info) -> User:
    """fetch and return user from post

    Returns:
        User -- related User Object
    """
    if not post.user:
        await post.fetch_related("user")
    return post.user


@MUTATION.field("createUser")
async def create_user(_root, _info, username: str, email: str, password: str) -> dict:
    """create a new user

    Arguments:
        username {str} -- login username
        email {str} -- user email address
        password {str} -- password in plain text (will be hashed)

    Returns:
        dict -- see CreateUserPayload
    """
    try:
        user = await User.get(username=username)
        return {"status": "FAILED", "error": "User name is already in use"}
    except DoesNotExist:
        pass

    hashed = bcrypt.hashpw(
        base64.b64encode(hashlib.sha256(password.encode()).digest()),
        bcrypt.gensalt()).decode()

    token_id = uuid.uuid4()

    user = await User.create(username=username, email=email, password=hashed, token_id=token_id)
    return {"status": "SUCCESSFUL", "user": user}


@MUTATION.field("createPost")
@convert_kwargs_to_snake_case
async def create_post(_root, info, title: str, body: str) -> dict:
    """create a new post for user

    emits event when new post is created

    Arguments:
        title {str} -- post's title
        body {str} -- post's body

    Returns:
        dict -- see CreatePostPayload
    """

    if not isinstance(info.context["request"].user, JWTUser):
        return {"status": "AUTHERROR", "error": "Please log in"}

    try:
        user = await User.get(id=info.context["request"].user.user_id)
    except DoesNotExist:
        return {"status": "FAILED", "error": "unable to create post, user does not exist"}

    post = await Post.create(user=user, title=title, body=body)
    PUBSUB.emit("new_post", post)

    return {"status": "SUCCESSFUL", "post": post}


@MUTATION.field("login")
async def log_in(_root, _info, username: str, password: str) -> dict:
    """returns token for successful log in

    Arguments:
        username {str} -- user name
        password {str} -- password plain text

    Returns:
        dict -- see LoginPayload
    """
    try:
        user = await User.get(username=username)
    except DoesNotExist:
        return {"status": "FAILED", "error": "unable to log in"}

    if bcrypt.checkpw(
            base64.b64encode(hashlib.sha256(password.encode()).digest()),
            user.password.encode()):

        # encoded web token (not encrypted, do not put sensitive data here)
        encoded_jwt = jwt.encode(
            {
                "id": user.id,
                "token_id": user.token_id.hex
            },
            str(JWT_SECRET_KEY),
            algorithm="HS256")
        return {"status": "SUCCESSFUL", "token": encoded_jwt.decode()}
    else:
        return {"status": "FAILED", "error": "unable to log in"}


@MUTATION.field("logout")
async def log_out(_root, info) -> bool:
    """Forces a user to log in again on ALL devices by generating new token id

    to "logout" user on the a single device, just clear jwt on that device
    """

    # user if not logged in
    if not isinstance(info.context["request"].user, JWTUser):
        return False

    token_id = uuid.uuid4()
    await User.get(id=info.context["request"].user.user_id).update(token_id=token_id)
    return True


@SUBSCRIPTION.source("newPost")
def subscribe_messages(_root, _info):
    """new post event listener"""
    return EventEmitterAsyncIterator(PUBSUB, "new_post")


@SUBSCRIPTION.field("newPost")
def push_message(post, _info):
    """return newly created post from event listener"""
    return post


@SUBSCRIPTION.source("count")
async def counter(_root, _info, limit: int):
    """counts to a given range

    Arguments:
        limit {int} -- counter will count up to the given limit
    """
    for i in range(limit):
        await asyncio.sleep(1)
        yield i


@SUBSCRIPTION.field("count")
def count(number, _info, **_kwargs):
    """returns current count number, starting at 1"""
    return number + 1


@APP.on_event("startup")
async def startup():
    """initialization steps"""
    await init_db()


@APP.on_event("shutdown")
async def shutdown():
    """clean up on shutdown"""
    await close_connections()

SCHEMA = make_executable_schema(SCHEMA, [MUTATION, QUERY, SUBSCRIPTION, POST])

GRAPHQL_SERVER = GraphQL(
    SCHEMA,
    debug=DEBUG,
    extensions=[ApolloTracingExtension],
)

APP.add_middleware(
    AuthenticationMiddleware,
    backend=JWTAuthBackend(),
    on_error=on_auth_error)
APP.add_route("/graphql/", GRAPHQL_SERVER)
APP.add_websocket_route("/graphql/", GRAPHQL_SERVER)
APP.debug = DEBUG
