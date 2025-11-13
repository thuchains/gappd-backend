from app.extensions import ma
from app.models import Posts
from marshmallow import fields

class PostSchema(ma.SQLAlchemyAutoSchema):
    photos = fields.Nested("PhotoSchema", many=True)
    exclude = ("file_data",)

    class Meta:
        model = Posts

post_schema = PostSchema()
posts_schema = PostSchema(many=True)
