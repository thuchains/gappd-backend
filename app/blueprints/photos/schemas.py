from app.extensions import ma
from app.models import Photos


class PhotoSchema(ma.SQLAlchemyAutoSchema):

    
    class Meta:
        model = Photos
        exclude = ("file_data",)

                  
photo_schema = PhotoSchema()
photos_schema = PhotoSchema(many=True)