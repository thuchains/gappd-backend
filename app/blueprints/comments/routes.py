from flask import request, jsonify
from app.models import db, Comments, Posts, Users
from app.extensions import limiter, cache
from app.blueprints.comments import comments_bp
from app.blueprints.comments.schemas import comment_schema, comments_schema
from marshmallow import ValidationError
from app.util.auth import encode_token, token_required
from werkzeug.security import generate_password_hash, check_password_hash


#Create comment
@comments_bp.route('', methods=['POST'])
@token_required
def create_comment():
    try:
        data = comment_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    new_comment = Comments(**data)
    db.session.add(new_comment)
    db.session.commit()
    return comment_schema.jsonify(new_comment), 201


#View all comments in a post
@comments_bp.route('/by-post/<int:post_id>', methods=['GET'])
def view_comments_of_post(post_id):
    if not db.session.get(Posts, post_id):
        return jsonify({"message": "Post not found"})
    
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page=1

    per_page = 40

    qry = (Comments.query.filter(Comments.post_id == post_id).order_by(Comments.created_at.asc(), Comments.id.asc()))
    
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": comments_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#Delete comment
@comments_bp.route('<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    user_id = request.user_id

    comment = db.session.get(Comments, comment_id)

    if not comment:
        return jsonify({"message": "Comment not found"}), 404
    
    post = db.session.get(Posts, comment.post_id)
    can_delete = (comment.user_id == user_id) or (post and post.user_id == user_id)
    if not can_delete:
        return jsonify({"message": "Forbidden, must be owner of comment to delete"}), 403
    
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": f"Successfully deleted comment"}), 200


#Update comment
@comments_bp.route('/<int:comment_id>', methods=['GET'])
@token_required
def update_comment(comment_id):
    user_id = request.user_id

    comment = db.session.get(Comments, comment_id)

    if not comment:
        return jsonify({"message": "Comment not found"}), 400
    
    if comment.user_id != user_id:
        return jsonify({"message": "Forbidden"}), 403
    
    try:
        comment_data = comment_schema.load(request.json)
    except ValidationError as e:
        return jsonify({"message": e.messages}), 400
    
    for key, value in comment_data.items():
        setattr(comment, key, value)

    db.session.commit()
    return comment_schema.jsonify(comment), 200





