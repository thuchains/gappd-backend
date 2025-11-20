from app.extensions import ma
from app.models import Posts
from marshmallow import fields
from app.blueprints.users.schemas import UserSchema

class PostSchema(ma.SQLAlchemyAutoSchema):
    photos = fields.Nested("PhotoSchema", many=True)
    exclude = ("file_data",)
    user = fields.Nested(UserSchema)

    class Meta:
        model = Posts
        include_relationships = True

post_schema = PostSchema()
posts_schema = PostSchema(many=True)
