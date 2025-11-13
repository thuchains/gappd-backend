from app.extensions import ma
from marshmallow import fields
from app.models import EventPosts

class EventPostSchema(ma.SQLAlchemyAutoSchema):
    cover_photo = fields.Nested("PhotoSchema")
    # exclude = ("file_data",)

    class Meta:
        model = EventPosts
        include_fk=True

event_post_schema = EventPostSchema()
event_posts_schema = EventPostSchema(many=True)
