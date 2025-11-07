from app.extensions import ma
from app.models import EventPosts

class EventPostSchema(ma.SQLAlchemyAutoSchema):

    class Meta:
        model = EventPosts

event_post_schema = EventPostSchema()
event_posts_schema = EventPostSchema(many=True)
