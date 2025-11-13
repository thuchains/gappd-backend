from app.extensions import ma
from marshmallow import fields
from app.models import Comments

class CommentSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested("UserSchema")
    class Meta:
        model = Comments
        include_fk = True

comment_schema = CommentSchema()
comments_schema = CommentSchema(many=True)
