from app.extensions import ma
from app.models import Comments

class CommentSchema(ma.SQLAlchemyAutoSchema):

    class Meta:
        model = Comments

comment_schema = CommentSchema()
comments_schema = CommentSchema(many=True)
