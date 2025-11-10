from flask import request, jsonify
from sqlalchemy import select, insert, delete, or_
from datetime import datetime, timezone
from app.models import db, EventPosts, Users, event_hosts, event_rsvps, HostRole, Photos
from app.extensions import limiter, cache
from app.blueprints.event_posts import event_posts_bp
from app.blueprints.event_posts.schemas import event_post_schema, event_posts_schema
from marshmallow import ValidationError
from app.util.auth import encode_token, token_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

#Create event post
@event_posts_bp.route('', methods=['POST'])
@token_required
def create_event_post():
    user_id = request.user_id

    try:
        is_multipart = bool(request.content_type and request.content_type.startswith("multipart/form-data"))
        if is_multipart:
            form = request.form
            payload = {
                "title": (form.get("title") or "").strip(),
                "description": (form.get("description") or "").strip(),
                "start_time": (form.get("start_time") or "").strip(),  # may be "YYYY-MM-DD" or ISO datetime
                "street_address": (form.get("street_address") or None),
                "city": (form.get("city") or "").strip(),
                "state": (form.get("state") or "").strip(),
                "zipcode": (form.get("zipcode") or "").strip(),
                "country": (form.get("country") or "").strip(),
                # "user_id": user_id,
            }
            start_time_value = payload.get("start_time")
            if start_time_value:
                if len(start_time_value) == 10 and start_time_value[4] == "-" and start_time_value[7] == "-":
                    payload["start_time"] = datetime.strptime(start_time_value, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
                else:
                    try:
                        dt = datetime.fromisoformat(start_time_value.replace("z", "+00:00"))
                    except ValueError:
                        return jsonify({"message": "Invalid start_time format"}), 400

                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    payload["start_time"] = dt

            try:
                data = event_post_schema.load(payload)
            except ValidationError as e:
                return jsonify(e.messages), 400
            
            cover_photo = request.files.get("cover_photo")
            if cover_photo and cover_photo.filename:
                photo = Photos(user_id=user_id, filename=secure_filename(cover_photo.filename), content_type=cover_photo.file.mimetype, file_data=cover_photo.read())
                db.session.add(photo)
                db.session.flush()

            event_post = EventPosts(**data)
            db.session.add(event_post)
            db.session.commit()
            return event_post_schema.jsonify(event_post), 201
      
        payload = request.get_json()
        if payload is None:
            return jsonify({"message": "Invalid JSON body"})
        payload["user_id"] = user_id

        start_time_value = (payload.get("start_time") or "").strip()
        if start_time_value:
            if len(start_time_value) == 10 and start_time_value[4] == "-" and start_time_value[7] =="-":
                payload["start_time"] = datetime.strptime(st_val, "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                )
            else:
                try:
                    dt = datetime.fromisoformat(start_time_value.replace("z", "+00:00"))
                except ValueError:
                    return jsonify({"message": "Invalid start_time format."})
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                payload["start_time"] = dt


        try: 
            data = event_post_schema.load(payload)
        except ValidationError as e:
            return jsonify(e.messages), 400
        
        event_post = EventPosts(**data)
        db.session.add(event_post)
        db.session.commit()
        return event_post_schema.jsonify(event_post), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Failed to create event post"}), 500
        
        


#View individual event post of user
@event_posts_bp.route('/<int:event_post_id>', methods=['GET'])
def read_event(event_post_id):
    event = db.session.get(EventPosts, event_post_id)
    if not event:
        return jsonify({"message": "Event not found"}), 404
    return event_post_schema.jsonify(event), 200


#Events I host
@event_posts_bp.route('/me/hosting', methods=['GET'])
@token_required
def my_hosting(user_id):
    user_id = request.user_id

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page=1

    per_page = 10

    qry = (db.session.query(EventPosts).join(event_hosts, EventPosts.id == event_hosts.c.event_post_id).filter(event_hosts.c.user_id == user_id).order_by(EventPosts.start_time.asc()))
    
    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": event_posts_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#View all event posts
@event_posts_bp.route('', methods=['GET', 'OPTIONS'])
def read_all_event_posts():
    if request.method == "OPTIONS":
        return ("", 204)
    event_posts = db.session.query(EventPosts). all()

    return jsonify(event_posts_schema.dump(event_posts)), 200


#Delete event post
@event_posts_bp.route('<int:event_post_id>', methods=['DELETE'])
@token_required
def delete_event_post(event_post_id):
    user_id = request.user_id
    event_post = db.session.get(EventPosts, event_post_id)
    if not event_post:
        return jsonify({"message": "Event post not found"}), 404
    
    role_row = db.session.execute(select(event_hosts.c.role).where(event_hosts.c.event_post_id == event_post_id, event_hosts.c.user_id == user_id)).first()
    role = role_row[0] if role_row else None

    if role != HostRole.owner:
        return jsonify({"message": "Must be owner to delete this event"}), 403

    db.session.delete(event_post)
    db.session.commit()
    return jsonify({"message": f"Successfully deleted event post"}), 200


#Update event post
@event_posts_bp.route('<int:event_post_id>', methods=['PUT'])
@token_required
def update_event_post(event_post_id):
    user_id = request.user_id
    event_post = db.session.get(EventPosts, event_post_id)
    if not event_post:
        return jsonify({"message": "Event post not found"}), 404
    
    is_host = db.session.execute(select(event_hosts.c.event_post_id == event_post_id, event_hosts.c.user_id == user_id)).first() is not None
    if not is_host:
        return jsonify({"message": "Forbidden, must be a host to edit"}), 403
    
    try:
        event_post_data = event_post_schema.load(request.json)
    except ValidationError as e:
        return jsonify({"message": e.messages}), 400
    
    for key, value in event_post_data.items():
        setattr(event_post, key, value)

    db.session.commit()
    return event_post_schema.jsonify(event_post), 200


#Add cohost
@event_posts_bp.route('/<int:event_post_id>/hosts/<int:target_id>', methods=['POST'])
@token_required
def add_cohost(user_id, target_id, event_post_id):
    owner_id = request.user_id

    role_row = db.session.execute(select(event_hosts.c.role).where(event_hosts.c.event_post_id == event_post_id, event_hosts.c.user_id == owner_id)).first()
    if not role_row or role_row[0] != HostRole.owner:
        return jsonify({"message": "Only the owner can add hosts"}), 403
    
    if not db.session.get(Users, target_id):
        return jsonify({"message": "User not found"}), 404
    
    exists = db.session.execute(select(event_hosts.c.user_id).where(event_hosts.c.event_post_id == event_post_id, event_hosts.c.user_id == target_id)).first()
    if exists:
        return jsonify({"message": "User is already a host"}), 200
    
    db.session.execute(insert(event_hosts).values(user_id=target_id, event_post_id=event_post_id, role=HostRole.cohost.value))
    db.session.commit()
    return jsonify({"message": "Successfully added cohost"}), 201


#Remove cohost
@event_posts_bp.route('/<int:event_post_id>/hosts/<int:target_id>', methods=['DELETE'])
@token_required
def remove_cohost(user_id, target_id, event_post_id):
    owner_id = request.user_id

    role_row = db.session.execute(select(event_hosts.c.role).where(event_hosts.c.event_post_id == event_post_id, event_hosts.c.user_id == owner_id)).first()
    if not role_row or role_row[0] != HostRole.owner:
        return jsonify({"message": "Only the owner can remove hosts"}), 403
    
    if target_id == owner_id:
        return jsonify({"message": "Owner cannot remove themselves"}), 400
    
    db.session.execute(delete(event_hosts).values(user_id=target_id, event_post_id=event_post_id, role=HostRole.cohost.value))
    db.session.commit()
    return jsonify({"message": "Successfully removed cohost"}), 201


#RSVP event
@event_posts_bp.route('/<int:event_post_id>/rsvp', methods=['POST'])
@token_required
def rsvp_event(event_post_id):
    user_id = request.user_id

    event = db.session.get(EventPosts, event_post_id)
    if not event:
        return jsonify({"message": "Event not found"}), 404
    
    exists = db.session.execute(select(event_rsvps.c.user_id).where(event_rsvps.c.user_id == user_id, event_rsvps.c.event_post_id == event_post_id)).first()
    if exists:
        return jsonify({"message": "Already RSVP'd to event"}), 200
    
    db.session.execute(insert(event_rsvps).values(user_id=user_id, event_post_id=event_post_id))
    db.session.commit()
    return jsonify({"message": "Successfully RSVP'd to event"}), 201


#UnRSVP event
@event_posts_bp.route('/<int:event_post_id>/rsvp', methods=['POST'])
@token_required
def unrsvp_event(event_post_id):
    user_id = request.user_id

    event = db.session.get(EventPosts, event_post_id)
    if not event:
        return jsonify({"message": "Event not found"}), 404

    
    db.session.execute(delete(event_rsvps).values(user_id=user_id, event_post_id=event_post_id))
    db.session.commit()
    return jsonify({"message": "Successfully removed RSVP"}), 201


#View event attendees
@event_posts_bp.route('/<int:event_post_id>/attendees', methods=['GET'])
def list_attendees(event_post_id):
    if not db.session.get(EventPosts, event_post_id):
        return jsonify({"message": "Event not found"}), 404
    
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page=1

    per_page = 40

    qry = (db.session.query(Users.id, Users.username, Users.profile_picture).join(event_rsvps.c.Users.id == event_rsvps.c.user_id).filter(event_rsvps.c.event_post_id == event_post_id).order_by(event_rsvps.c.created_at.desc(), Users.id.desc()))
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


#Search events
@event_posts_bp.route('/search', methods=['GET'])
def search_events():
    query_params = (request.args.get("query_params") or "").strip()
    city = (request.args.get("city") or "").strip()
    state = (request.args.get("state") or "").strip()
    country = (request.args.get("country") or "").strip()
    zipcode = (request.args.get("zipcode") or "").strip()

    #grabbed from and to for datetime format from chatgpt
    now = datetime.now(timezone.utc)
    from_param = request.args.get("from")
    to_param = request.args.get("to")
    try:
        start_from = datetime.fromisoformat(from_param) if from_param else now
        start_to = datetime.fromisoformat(to_param) if to_param else None
    except ValueError:
        return jsonify({"message": "Invalid 'from' or 'to' datetime format"}), 400

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page=1

    per_page = 10

    qry = EventPosts.query
    if query_params:
        qry = qry.filter(or_(EventPosts.title.ilike(f"%{query_params}%"), EventPosts.description.ilike(f"%{query_params}%")))
    if city:
        qry = qry.filter(EventPosts.city.ilike(f"%{city}%"))
    if state:
        qry = qry.filter(EventPosts.state.ilike(f"%{state}%"))
    if country:
        qry = qry.filter(EventPosts.country.ilike(f"%{country}%"))
    if zipcode:
        qry = qry.filter(EventPosts.zipcode.ilike(f"%{zipcode}%"))
    
    qry = qry.filter(EventPosts.start_time >= start_from)
    if start_to:
        qry = qry.filter(EventPosts.start_time <= start_to)

    qry = qry.order_by(EventPosts.start_time.asc())

    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": event_posts_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#View my RSVPs
@event_posts_bp.route('/me/rsvps', methods=['GET'])
@token_required
def my_rsvps(user_id):
    user_id = request.user_id

    range = (request.args.get("range") or "upcoming").lower()

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page=1

    per_page = 10

    now = datetime.now(timezone.utc)

    qry = (db.session.query(EventPosts).join(event_rsvps, EventPosts.id == event_rsvps.c.event_post_id).filter(event_rsvps.c.user_id == user_id))

    if range == "upcoming":
        qry = qry.filter(EventPosts.start_time >= now).order_by(EventPosts.start_time.asc())
    elif range == "past":
        qry = qry.filter(EventPosts.start_time < now).order_by(EventPosts.start_time.desc())
    else:
        qry = qry.order_by(EventPosts.start_time.asc())

    pagination = qry.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": event_posts_schema.dump(pagination.items),
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages
    }), 200


#Upload event post cover photo
@event_posts_bp.route('/<int:event_post_id>/cover', methods=['POST'])
@token_required
def upload_event_cover(event_post_id):
    user_id = request.user_id

    event = db.session.get(EventPosts, event_post_id)
    if not event:
        return jsonify({"message": "Event post not found"}), 404
    if event.user_id != user_id:
        return jsonify({"message": "Forbidden, not allowed to modify this event"}), 403
    
    if "photo" not in request.files:
        return jsonify({"message": "No file provided"}), 400
    file = request.files["photo"]
    if not file or file.filename == "":
        return jsonify({"message": "No file selected"}), 400
    
    filename = secure_filename(file.filename)
    old_cover_id = event.cover_photo_id 

    file_data = file.read()

    try:
        photo = Photos(
            user_id=user_id,
            filename=filename,
            content_type=file.mimetype or "image/jpeg",
            file_data=file_data
        )
        db.session.add(photo)
        db.session.flush()

        event.cover_photo_id = photo.id
        db.session.add(event)

        if old_cover_id:
            old = db.session.get(Photos, old_cover_id)
            if old and old.user_id == user_id:
                db.session.delete(old)

        db.session.commit()

        return jsonify({
            "message": "Event cover photo updated",
            "cover": {
                "photo_id": photo.id,
                "filename": photo.filename,
                "content_type": photo.content_type
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Event cover picture upload failed"}), 500










