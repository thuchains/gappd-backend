from app.extensions import ma
from app.models import Posts

class PostSchema(ma.SQLAlchemyAutoSchema):

    class Meta:
        model = Posts

post_schema = PostSchema()
posts_schema = PostSchema(many=True)
