"""set up of db models"""
from tortoise import Tortoise, fields
from tortoise.models import Model


async def init_db():
    """initialize the db"""
    await Tortoise.init(
        db_url='sqlite://db.sqlite3',
        modules={'models': ['backend.models']}
    )
    # Generate the schema
    await Tortoise.generate_schemas()


async def close_connections():
    """close connections"""
    await Tortoise.close_connections()


class User(Model):
    """User Model

    id field is auto incremented

    Arguments:
        name {fields.CharField} -- name of user
    """
    # Defining `id` field is optional, it will be defined automatically
    # if you haven't done it yourself
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)


class Post(Model):
    """Post Model

    id field is auto incremented

    Arguments:
        title {str} -- post's title line
        body {str} -- post body
        user_id {int} -- user_id that post related to
        user {User} -- user object, can be used instead of user_id
    """
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=50)
    body = fields.CharField(max_length=255)
    user = fields.ForeignKeyField('models.User', related_name='posts')
