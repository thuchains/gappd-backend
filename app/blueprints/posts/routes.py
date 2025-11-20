from flask import request, jsonify, url_for
from sqlalchemy import select, insert, delete, func, exists
from sqlalchemy.orm import selectinload, joinedload
from app.models import db, Posts, Users, follows, post_likes, Photos
from app.extensions import limiter, cache
from app.blueprints.posts import posts_bp
from app.blueprints.posts.schemas import posts_schema, post_schema
from app.blueprints.users.schemas import user_schema
from marshmallow import ValidationError
from app.util.auth import encode_token, token_required, SECRET_KEY
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from jose import jwt as jose_jwt, exceptions as jose_exceptions

#Create post
@posts_bp.route('', methods=['POST'])
@token_required
def create_post():
    user_id = request.user_id
    files = request.files


    if request.content_type and request.content_type.startswith("multipart/form-data"):
        caption = request.form.get("caption")
        location = request.form.get("location")
        photo_ids = request.form.getlist("photo_ids")

        new_post = Posts(user_id=user_id, caption=caption, location=location)
        db.session.add(new_post)
        db.session.commit()

        for photo_id in photo_ids:
            try:
                photo_id_to_int = int(photo_id)
            except (TypeError, ValueError):
                db.session.rollback()
                return jsonify({"message": f"Invalid photo id '{photo_id}'"}), 400
        
            photo = Photos.query.get(photo_id_to_int)
            if not photo:
                db.session.rollback()
                return jsonify({"message": f"Photo_id `{photo_id_to_int}` not found"}), 404
            
            photo.post_id = new_post.id
            photo.user_id = user_id

        files = request.files.getlist("files")
        for file in files or []:
            if not file or file.filename == "":
                continue
            photo = Photos(user_id=user_id, post_id=new_post.id, filename=secure_filename(file.filename), content_type=file.mimetype or "image/jpeg", file_data=file.read())
            db.session.add(photo)

        db.session.commit()
        return post_schema.jsonify(new_post), 201
    
    payload = request.get_json()
    if payload is None:
        return jsonify({"message": "Invalid JSON body"}), 400
    payload["user_id"] = user_id

    try:
        data = post_schema.load(payload)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    post = Posts(**data)
    db.session.add(post)
    db.session.commit()
    return post_schema.jsonify(post), 201
  


#Search post by key words in caption
@posts_bp.route('/search', methods=['GET'])
def search_posts():
    if request.is_json:
        payload = request.get_json()
        query_params = (payload.get("query_params") or "").strip()
        page = payload.get("page", 1)
        per_page = payload.get("per_page", 20)
    else:
        query_params = request.args.get("query_params", "").strip()
        page = request.args.get("page", 1)
        per_page = request.args.get("per_page", 20)

    if not query_params:
        return jsonify({"message": "Query parameter is required"}), 400
    
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 20

    qry = Posts.query.filter(Posts.caption.ilike(f"%{query_params}%")).order_by(Posts.created_at.desc())
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False) #raises not found error if user asks for out of range page
    
    return jsonify({
        "items": posts_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#View individual post
@posts_bp.route('/<int:post_id>', methods=['GET'])
def get_post(post_id):
    post = (db.session.query(Posts).options(joinedload(Posts.user)).get(post_id))
    if not post: 
        return jsonify({"message": "Post not found"}), 404

    request_user_id = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            try:
                decoded = jose_jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                request_user_id = int(decoded.get("sub"))
            except (jose_exceptions.JWTError, ValueError):
                request_user_id = None

    data = post_schema.dump(post)
    if post.user:
        author_data = user_schema.dump(post.user)
        if request_user_id and post.user.id != request_user_id:
            is_following = db.session.execute(
                select(exists().where(
                    (follows.c.follower_id == request_user_id) &
                    (follows.c.followed_id == post.user.id)
                ))
            ).scalar()
            author_data["is_following"] = bool(is_following)
        else:
            author_data["is_following"] = False
        data["author"] = author_data
    return jsonify(data), 200


#View posts in feed of people user follows(like a for you page)
@posts_bp.route('/feed', methods=['GET'])
@token_required
def get_feed():
    # ============== my original route ==============
    # user_id = request.user_id

    # page = max(int(request.args.get("page", 1)), 1)
    # per_page = 10

    # followed_ids = db.session.execute(select(follows.c.followed_id).where(follows.c.follower_id == user_id)).scalars().all()

    # visible_user_ids = list(set((followed_ids or []) + [user_id]))
    
    # qry = db.session.query(Posts).filter(Posts.user_id.in_(visible_user_ids)).order_by(Posts.created_at.desc())
    # pagination = qry.paginate(page=page, per_page=per_page, error_out=False)

    # return jsonify({
    #     "items": posts_schema.dump(pagination.items),
    #     "page": pagination.page,
    #     "per_page": pagination.per_page,
    #     "total": pagination.total,
    #     "pages": pagination.pages

    # }), 200
    # ============== new route with help from chatGPT bc I couldn't get it to return my profile picture avatar ===========

    user_id = request.user_id

    page = max(int(request.args.get("page", 1)), 1)
    per_page = 10

    followed_ids = db.session.execute(
        select(follows.c.followed_id).where(follows.c.follower_id == user_id)
    ).scalars().all()

    visible_user_ids = set(followed_ids + [user_id])

    if not visible_user_ids:
        return jsonify({
            "items": [],
            "page": page,
            "per_page": per_page,
            "total": 0,
            "pages": 0
        }), 200

    qry = (
        db.session.query(Posts)
        .filter(Posts.user_id.in_(visible_user_ids))
        .order_by(Posts.created_at.desc())
    )

    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)

    posts = pagination.items
    posts_data = posts_schema.dump(posts)

    followed_set = set(followed_ids)

    for idx, post in enumerate(posts):
        p = posts_data[idx]
        author = post.user  

        if author is not None:
            p["author"] = {
                "id": author.id,
                "username": author.username,
                "first_name": author.first_name,
                "last_name": author.last_name,
                "profile_photo_id": author.profile_photo_id,
                "is_following": bool(author.id in followed_set),
            }
        else:
            p.setdefault("author", {
                "id": p.get("user_id"),
                "username": p.get("username"),
                "first_name": None,
                "last_name": None,
                "profile_photo_id": None,
                "is_following": False,
            })
    
        p["author_is_following"] = p["author"]["is_following"]

    return jsonify({
        "items": posts_data,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#View all post of a user(like viewing their profile)
@posts_bp.route('/by-user/<int:user_id>', methods=['GET'])
def get_posts_by_user(user_id):
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = min(max(int(request.args.get("per_page", 15)), 1), 50)
    except ValueError:
        per_page = 15

    posts = (select(Posts).where(Posts.user_id == user_id).order_by(Posts.created_at.desc()))

    pagination = db.paginate(posts, page=page, per_page=per_page, error_out=False)
        
    return jsonify({
        "items": posts_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#Delete post
@posts_bp.route('/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(post_id):
    user = request.user_id
    post = db.session.get(Posts, post_id)
    if not post:
        return jsonify({"message": "Post not found"}), 404
    
    db.session.delete(post)
    db.session.commit()
    return jsonify({"message": f"Successfully deleted post"})


#Update post
@posts_bp.route('/<int:post_id>', methods=['PUT'])
@token_required
def update_post(post_id):
    user_id = request.user_id
    post = db.session.get(Posts, post_id)
    if not post:
        return jsonify({"message": "Post not found"}), 400
    
    if post.user_id != user_id:
        return jsonify({"message": "Forbidden, must be account owner to edit post."})
    
    try:
        post_data = post_schema.load(request.json or {}, partial=True)
    except ValidationError as e:
        return jsonify({"message": e.messages}), 400
    
    for key, value in post_data.items():
        setattr(post, key, value)

    db.session.commit()
    return post_schema.jsonify(post), 200


#Like a post
@posts_bp.route('/<int:post_id>/like', methods=['POST'])
@token_required
def like_post(post_id):
    user_id = request.user_id

    post = db.session.get(Posts, post_id)
    if not post:
        return jsonify({"message": "Post not found"}), 404
    
    liked = db.session.execute(
        select(
            post_likes.c.user_id).where(
                post_likes.c.user_id == user_id, 
                post_likes.c.post_id == post_id
                )
            ).first()
    
    if liked:
        return jsonify({"message": "Post already liked"}), 200
    
    db.session.execute(insert(post_likes).values(user_id=user_id, post_id=post_id))
    db.session.commit()
    return jsonify({"message": "Liked post"}), 201


#Unlike post
@posts_bp.route('/<int:post_id>/like', methods=['DELETE'])
@token_required
def unlike_post(post_id):
    user_id = request.user_id

    post = db.session.get(Posts, post_id)
    if not post:
        return jsonify({"message": "Post not found"}), 404
    
    db.session.execute(
        delete(post_likes).where(
            post_likes.c.user_id ==user_id,
            post_likes.c.post_id == post_id
        )
    )
    db.session.commit()
    return jsonify({"message": "Unliked post"}), 200


#List of users who liked the post
@posts_bp.route('/<int:post_id>/likes', methods=['GET'])
def list_post_likes(current_user, post_id):
    post = db.session.get(Posts, post_id)
    if not post:
        return jsonify({"message": "Post not found"}), 404
    
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page=1

    per_page = 40

    qry = (db.session.query(Users.id, Users.username, Users.profile_picture).join(post_likes, Users.id == post_likes.c.user_id).filter(post_likes.c.post_id == post_id).order_by(post_likes.c.created_at.desc(), Users.id.desc()))

    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)

    items =[]
    for user in pagination.items:
        items.append({
            "id": user.id,
            "username": user.username,
            "profile_picture": user.profile_picture
        })

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200



