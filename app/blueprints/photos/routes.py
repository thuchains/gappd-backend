import io
from flask import request, jsonify, Flask, send_file
from sqlalchemy import select, insert, delete, func
from sqlalchemy.orm import selectinload
from app.models import db, Posts, Users, Photos, EventPosts
from app.extensions import limiter, cache
from app.blueprints.photos import photos_bp
from app.blueprints.photos.schemas import photo_schema, photos_schema
from marshmallow import ValidationError
from app.util.auth import encode_token, token_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

#Upload photo
@photos_bp.route('/upload', methods=['POST'])
@token_required
def upload_post_photo(post_id):
    user_id = request.user_id

    post = db.session.get(Posts, post_id)

    if not post:
        return jsonify({"message": "Post not found"}), 404
    if post.user_id != user_id:
        return jsonify({"message": "Forbidden, cannot add photos to another user's post"}), 403
    

    try:
        files = []
        if 'photo' in request.files:
            files = request.files.getlist('photos')
        elif 'photo' in request.files:
            files = [request.files['photo']]
        else:
            return jsonify({"message": "No file provided"}), 400
        
        saved = []
        for file in files:
            if not file or file.filename == '':
                continue

            photo = Photos(
                user_id=user_id,
                post_id=post_id,
                filename=secure_filename(file.filename),
                content_type = file.mimetype or 'image/jpeg',
                file_data = file.read()
            )
        if not saved:
            db.session.rollback()
            return jsonify({"message": "No valid files"}), 400
        
        db.session.commit()
        return jsonify({"message": "Upload successfull", "photos": saved})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Upload failed"}), 500


#Delete photo
@photos_bp.route('/<int:photo_id>', methods=['DELETE'])
@token_required
def delete_photo(photo_id):
    user_id = request.user_id

    photo = db.session.get(Photos, photo_id)
    if not photo:
        return jsonify({"message": "Photo not found"}), 404
    if photo.user_id != user_id:
        return jsonify({"message": "Forbidden, only owner can delete photo"}), 403
    try:
        db.session.delete(photo)
        db.session.commit()
        return jsonify({"message": "Successfully deleted photo"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Delete failed"}), 500




#============ probably don't need since photos can be grabbed from posts routes ==============
# #Get photo
# @photos_bp.route('/api/photo/<int:photo_id>', methods=['GET'])
# def get_photo(photo_id):
#     photo = db.session.get(Photos, photo_id)

#     if not photo:
#         return jsonify({"message": "Photo not found"}), 404
#     return send_file(
#         io.BytesIO(photo.file_data),
#         mimetype=photo.content_type,
#         as_attachment=False
#     )


# #View all photos
# @photos_bp.route('/api/photos', methods=['GET'])
# def list_photos():
#     photos = db.session.query(Photos).all()
#     return jsonify([Photos.to_dict() for photo in photos])


    
        


