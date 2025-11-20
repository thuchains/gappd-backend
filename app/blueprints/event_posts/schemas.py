from app.extensions import ma
from marshmallow import fields
from app.models import EventPosts
from app.blueprints.users.schemas import UserSchema


class EventPostSchema(ma.SQLAlchemyAutoSchema):
    cover_photo = fields.Nested("PhotoSchema")
    hosts = fields.Nested(
        UserSchema,
        many=True,
        only=("id", "username", "profile_photo_id", "first_name", "last_name"),
    )

    class Meta:
        model = EventPosts
        include_fk = True
        include_relationships = True


event_post_schema = EventPostSchema()
event_posts_schema = EventPostSchema(many=True)
