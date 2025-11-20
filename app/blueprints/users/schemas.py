from app.extensions import ma
from app.models import Users

class UserSchema(ma.SQLAlchemyAutoSchema):

    class Meta:
        model = Users
        include_fk = True

user_schema = UserSchema()
users_schema = UserSchema(many=True)
user_login_schema = UserSchema(only=['email', 'password'])
    
