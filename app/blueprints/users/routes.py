import io
from flask import request, jsonify, send_file
from sqlalchemy import select, insert, delete, exists, func
from app.models import db, Users, follows, Photos, event_hosts, event_rsvps, HostRole, EventPosts, Posts, Comments, post_likes
from app.extensions import limiter, cache
from app.blueprints.users import users_bp
from app.blueprints.users.schemas import user_schema, users_schema, user_login_schema
from marshmallow import ValidationError
from app.util.auth import encode_token, token_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

#Login
@users_bp.route('/login',  methods=['POST'])
def login():
    try:
        data = user_login_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    user = db.session.query(Users).where(Users.email==data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        token = encode_token(user.id)
        return jsonify({
            "message": f"Welcome {user.first_name} {user.last_name}",
            "token": token,
            "id": user.id
        }), 200
    
    return jsonify("Invalid email or password"), 403

#Create user
@users_bp.route('', methods=['POST'])
def create_user():
    try: 
        data = user_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    print("load user schema")
    
    if db.session.query(Users).filter(Users.email == data["email"]).first():
        return jsonify({"message": "Email already taken"}), 409
    if db.session.query(Users).filter(Users.username == data["username"]).first():
        return jsonify({"message": "Username already taken"}), 409
    
    data['password'] = generate_password_hash(data['password'])
    print("hashed password")
    new_user = Users(**data)
    db.session.add(new_user)
    db.session.commit()

    print("created user")

    response = user_schema.dump(new_user)
    return jsonify(response), 201


#View another user (public profile)
@users_bp.route('/<string:username>', methods=['GET'])
def read_user(username):
    # user_id = request.user_id
    user_id = getattr(request, "user_id", None)
    target = db.session.execute(select(Users).where(Users.username == username)).scalar_one_or_none()
    if not target:
        return jsonify({"message": "User not found"}), 404
    
    posts_count = (db.session.execute(select(func.count(Posts.id)).where(Posts.user_id == target.id)).scalar() or 0)
    events_count = (db.session.execute(select(func.count(EventPosts.id)).select_from(EventPosts).join(event_hosts, event_hosts.c.event_post_id == EventPosts.id).where(event_hosts.c.user_id == target.id)).scalar() or 0)
    followers_count = (db.session.execute(select(func.count(follows.c.follower_id)).where(follows.c.followed_id == target.id)).scalar() or 0)
    following_count = (db.session.execute(select(func.count(follows.c.followed_id)).where(follows.c.follower_id == target.id)).scalar() or 0)
    
    is_following = False
    if user_id and user_id != target.id:
        is_following = db.session.execute(select(exists().where((follows.c.follower_id == user_id) & (follows.c.followed_id == target.id)))).scalar()
    
    payload = user_schema.dump(target)
    payload["counts"] = {
        "posts": posts_count,
        "events": events_count,
        "followers": followers_count,
        "following": following_count
    }
    payload["is_following"] = bool(is_following)
    return jsonify(payload), 200


#View self
@users_bp.route('/me', methods=['GET'])
@token_required
def read_me():
    print(request.user_id)
    user_id = request.user_id
    user = db.session.get(Users, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    posts_count = db.session.execute(select(func.count(Posts.id)).where(Posts.user_id == user.id)).scalar() or 0
    events_count = db.session.execute(select(func.count(EventPosts.id)).select_from(EventPosts).join(event_hosts, event_hosts.c.event_post_id == EventPosts.id).where(event_hosts.c.user_id == user.id)).scalar() or 0
    followers_count = db.session.execute(select(func.count(follows.c.follower_id)).where(follows.c.followed_id == user.id)).scalar() or 0
    following_count = db.session.execute(select(func.count(follows.c.followed_id)).where(follows.c.follower_id == user.id)).scalar() or 0

    payload = user_schema.dump(user)
    payload["counts"] = {
        "posts": posts_count,
        "events": events_count,
        "followers": followers_count,
        "following": following_count,
    }
    payload["is_following"] = False #users can't follow themselves

    return jsonify(payload), 200


#Delete user
@users_bp.route('/me', methods=['DELETE'])
@token_required
def delete_user():
    user_id = request.user_id
    user = db.session.get(Users, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    try:
        db.session.execute(follows.delete().where(follows.c.follower_id == user_id))
        db.session.execute(follows.delete().where(follows.c.followed_id == user_id))
        db.session.execute(event_rsvps.delete().where(event_rsvps.c.user_id == user_id))
        db.session.execute(event_hosts.delete().where(event_hosts.c.user_id == user_id))

        hostless_event_ids = db.session.query(EventPosts.id).outerjoin(event_hosts, EventPosts.id == event_hosts.c.event_post_id).filter(event_hosts.c.event_post_id.is_(None)).all()
        if hostless_event_ids:
            ids = [row[0] for row in hostless_event_ids]
            cover_photo_ids = db.session.query(EventPosts.cover_photo_id).filter(EventPosts.id.in_(ids), EventPosts.cover_photo_id.isnot(None)).all()
            if cover_photo_ids:
                db.session.execute(Photos.__table__.delete().where(Photos.id.in_([p[0] for p in cover_photo_ids])))
            db.session.query(EventPosts).filter(EventPosts.id.in_(ids)).delete(synchronize_session=False)
        post_ids = [post_id for (post_id,) in db.session.query(Posts.id).filter(Posts.user_id == user_id).all()]
        if post_ids:
            db.session.execute(post_likes.delete().where(post_likes.c.post_id.in_(post_ids)))
            db.session.query(Comments).filter(Comments.post_id.in_(post_ids)).delete(synchronize_session=False)
            db.session.query(Photos).filter(Photos.post_id.in_(post_ids)).delete(synchronize_session=False)
            db.session.query(Posts).filter(Posts.id.in_(post_ids)).delete(synchronize_session=False)

        db.session.query(Comments).filter(Comments.user_id == user_id).delete(synchronize_session=False)
        db.session.execute(post_likes.delete().where(post_likes.c.user_id == user_id))
        db.session.query(Photos).filter(Photos.user_id == user_id).delete(synchronize_session=False)

        user.profile_photo_id = None
        db.session.add(user)
        db.session.flush()

        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": f"Successfully deleted user {user_id}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Failed to delete user"}), 500


#Update user
@users_bp.route('/me', methods=['PUT'])
@token_required
def update_user():
    user_id = request.user_id
    user = db.session.get(Users, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    try: 
        user_data = user_schema.load(request.json or {}, partial=True)
    except ValidationError as e:
        return jsonify({"message": e.messages}), 400
    
    new_email = user_data.get("email")
    if new_email and db.session.query(Users).filter(Users.email == new_email, Users.id != user_id).first():
        return jsonify({"message": "Email already taken"}), 409
    
    new_username = user_data.get("username")
    if new_username and db.session.query(Users).filter(Users.username == new_username, Users.id != user_id).first():
        return jsonify({"message": "Username already taken"}), 409

    if 'password' in user_data:
        user_data['password'] = generate_password_hash(user_data['password'])

    for key, value in user_data.items():
        setattr(user, key, value)

    db.session.commit()
    return user_schema.jsonify(user), 200


#Search user by username
@users_bp.route('/search', methods=['GET'])
def search_user():
    # payload = request.get_json()
    # username = request.args.get("username") or payload.get("username")
    # if not username:
    #     return jsonify({"message": "Username is required"}), 400
    
    # user = db.session.execute(select(Users).where(Users.username == username)).scalars().first()
    
    # if not user:
    #     return jsonify({"message": "User not found"}), 404
    
    # return jsonify({
    #     "id": user.id,
    #     "username": user.username,
    #     "profile_photo_id": user.profile_photo_id
    # }), 200

    username = (request.args.get("username") or request.args.get("q") or "").strip()
    
    if not username:
        return jsonify({"message": "Username is required"}), 400

    like_pattern = f"%{username}%"

    users = (
        db.session.query(Users)
        .filter(Users.username.ilike(like_pattern))
        .order_by(Users.username.asc())
        .limit(30)
        .all()
    )

    # Always return an array, even if empty
    return jsonify({
        "users": users_schema.dump(users)
    }), 200

#Follow a user
@users_bp.route('/<int:target_id>/follow', methods=['POST'])
@token_required
def follow_user(target_id):
    follower_id = request.user_id
    if follower_id == target_id:
        return jsonify({"message": "You cannot follow yourself"}), 400
    
    if not db.session.get(Users, target_id):
        return jsonify({"message": "User not found"}), 404
    
    exists = db.session.execute(select(follows.c.follower_id).where(follows.c.follower_id == follower_id, follows.c.followed_id == target_id)).first()
    if exists:
        return jsonify({"message": "Already following"}), 200
    
    db.session.execute(insert(follows).values(follower_id=follower_id, followed_id=target_id))
    db.session.commit()
    return jsonify({"message": "Successfully followed"}), 201


#Unfollow a user
@users_bp.route('/<int:target_id>/follow', methods=['DELETE'])
@token_required
def unfollow_user(target_id):
    follower_id = request.user_id
    if not db.session.get(Users, target_id):
        return jsonify({"message": "User not found"}), 404
    
    unfollow = db.session.execute(follows.delete().where(follows.c.follower_id == follower_id, follows.c.followed_id == target_id))
    db.session.commit()
    if unfollow.rowcount == 0:
        return jsonify({"message": "Not following"}), 200
    return jsonify({"message": "Successfully unfollowed"}), 200


#List followers
@users_bp.route('/<int:user_id>/followers', methods=['GET'])
def list_followers(user_id):
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 30

    qry = (db.session.query(Users).join(follows, Users.id == follows.c.follower_id).filter(follows.c.followed_id == user_id).order_by(Users.username.asc()))
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": users_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#List following
@users_bp.route('/<int:user_id>/following', methods=['GET'])
def list_following(user_id):
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 30

    qry = (db.session.query(Users).join(follows, Users.id == follows.c.followed_id).filter(follows.c.follower_id == user_id).order_by(Users.username.asc()))
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": users_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#Upload profile picture
@users_bp.route('/me/avatar', methods=['POST'])
@token_required
def upload_profile_photo():
    user_id = request.user_id

    user = db.session.get(Users, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({"message": "No file selected"}), 400
    
    if "photo" not in request.files:
        return jsonify({"message": "No file provided"}), 400
    
    filename = secure_filename(file.filename)

    old_photo_id = user.profile_photo_id

    file_data = file.read()

    try:
        photo = Photos(
            user_id=user_id,
            filename=filename,
            content_type=file.mimetype or 'image/jpeg',
            file_data=file_data
        )
        db.session.add(photo)
        db.session.flush()

        user.profile_photo_id = photo.id
        db.session.add(user)

        if old_photo_id:
            old = db.session.get(Photos, old_photo_id)
            if old and old.user_id == user_id:
                db.session.delete(old)

        db.session.commit()

        return jsonify({
            "message": "Successfully updated profile picture",
            "profile_picture": {
                "photo_id": photo.id,
                "filename": photo.filename,
                "content_type": photo.content_type
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Profile picture upload failed"}), 500
    

#Delete profile picture
@users_bp.route('/me/avatar', methods=['DELETE'])
@token_required
def delete_profile_photo():
    user_id = request.user_id

    user = db.session.get(Users, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    if not user.profile_photo_id:
        return jsonify({"message": "No profile picture set"}), 400
    
    try:
        old = db.session.get(Photos, user.profile_photo_id)
        user.profile_photo_id = None
        db.session.add(user)

        if old and old.user_id == user_id:
            db.session.delete(old)

        db.session.commit()
        return jsonify({"message": "Successfully removed profile picture"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Failed to remove profile picture"}), 500


#Get profile picture
@users_bp.route('/<int:user_id>/avatar', methods=['GET'])
def get_profile_photo(user_id):
    user = db.session.get(Users, user_id)
    if not user or not user.profile_photo_id:
        return jsonify({"message": "Profile picture not found"}), 404
    
    photo = db.session.get(Photos, user.profile_photo_id)
    if not photo:
        return jsonify({"message": "Profile photo not found"}), 404
    
    return send_file(
        io.BytesIO(photo.file_data),
        mimetype=photo.content_type or "image/jpeg",
        as_attachment=False,
        download_name=photo.filename or f"user_{user_id}_avatar.jpg",
        last_modified=photo.upload_date
    )


