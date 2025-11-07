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
@photos_bp.route('/api/upload', methods=['POST'])
@token_required
def upload_post_photo(post_id):
    user_id = request.user_id

    post = db.session.get(Posts, post_id)

    if not post:
        return jsonify({"message": "Post not found"}), 404
    if post.user_id != user_id:
        return jsonify({"message": "Forbidden, cannot add photos to another user's post"}), 403
    

    try:
        if 'photo' not in request.files:
            return jsonify({"message": "No file provided"}), 400
        
        file = request.files['photo']

        if not file or file.filename == '':
            return jsonify({"message": "No file selected"}), 400
        
        file_data = file.read()

        photo = Photos(
            user_id=user_id,
            post_id=post_id,
            filename=file.filename,
            content_type = file.content_type or 'image/jpeg',
            file_data = file_data
        )

        db.session.add(photo)
        db.session.commit()
        return jsonify({
            "message": "Upload successful",
            "photo_id": photo.id,
            "filename": photo.filename
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Upload failed"}), 500

    # file = request.files.get("file")
    # if not file or not file.filename:
    #     return jsonify({"message": "File required"}), 400
    
    # post_id = request.form.get("post_id", type=int)
    # event_post_id = request.form.get("event_post_id", type=int)

    # if post_id:
    #     post = db.session.get(Posts, post_id)
    #     if not post or post.user_id != user_id:
    #         return jsonify({"message": "Invalid post_id"}), 400
        
    # if event_post_id:
    #     event = db.session.get(EventPosts, event_post_id)
    #     if not event:
    #         return jsonify({"message": "Invalid event_post_id"}), 400
        
    # photo = Photos(user_id=user_id, post_id=post_id, filename=secure_filename(file.filename), content_type=file.mimetype, file_data=file.read())

    # db.session.add(photo)
    # db.session.commit()
    # return jsonify({
    #     "id": photo.id,
    #     "filename": photo.filename,
    #     "content_type": photo.content_type,
    #     "upload_date": photo.upload_date.isoformat()
    # }), 201


#Delete photo
@photos_bp.route('/api/photo/<int:photo_id>', methods=['DELETE'])
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


    
        


