from app.extensions import ma
from marshmallow import fields
from app.models import EventPosts

class EventPostSchema(ma.SQLAlchemyAutoSchema):
    cover_photo = fields.Nested("PhotoSchema")

    class Meta:
        model = EventPosts

event_post_schema = EventPostSchema()
event_posts_schema = EventPostSchema(many=True)
