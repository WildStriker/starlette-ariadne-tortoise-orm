"""app and graphql resolver set up in this module"""
import asyncio
import os

from ariadne import (ObjectType, SubscriptionType,
                     convert_kwargs_to_snake_case, load_schema_from_path)
from ariadne.asgi import GraphQL
from ariadne.contrib.tracing.apollotracing import ApolloTracingExtension
from ariadne.executable_schema import make_executable_schema
from graphql.pyutils import EventEmitter, EventEmitterAsyncIterator
from starlette.applications import Starlette
from tortoise.exceptions import DoesNotExist

from .models import Post, User, close_connections, init_db

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
        await post.fetch_related('user')
    return post.user


@MUTATION.field("createUser")
async def create_user(_root, _info, name: str) -> User:
    """create a new user

    Arguments:
        name {str} -- user's name

    Returns:
        User -- created User Object
    """
    user = await User.create(name=name)
    return user


@MUTATION.field("createPost")
@convert_kwargs_to_snake_case
async def create_post(_root, _info, user_id: int, title: str, body: str) -> Post:
    """create a new post for user

    emits event when new post is created

    Arguments:
        user_id {int} -- user id for post
        title {str} -- post's title
        body {str} -- post's body

    Returns:
        Post -- create Post Object
    """
    try:
        user = await User.get(id=user_id)
    except DoesNotExist:
        return {'status': False, 'error': 'unable to create post, user does not exist'}

    post = await Post.create(user=user, title=title, body=body)
    PUBSUB.emit("new_post", post)

    return {'status': True, 'post': post}


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
    debug=True,
    extensions=[ApolloTracingExtension],
)


APP.add_route("/graphql/", GRAPHQL_SERVER)
APP.add_websocket_route("/graphql/", GRAPHQL_SERVER)
APP.debug = True
