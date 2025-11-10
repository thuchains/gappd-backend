from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum
from sqlalchemy import String, Integer, ForeignKey, DateTime, Table, Column, Date, Enum as EnumType, CheckConstraint, func, LargeBinary
from datetime import datetime, date



class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class = Base)

class HostRole(enum.Enum):
    owner = "owner"
    cohost = "cohost"


follows = Table(
    "follows",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("followed_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("follower_id <> followed_id", name="check_no_self_follow")
)

post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
)

# table presennce = GOING
event_rsvps = Table(
    "event_rsvps",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("event_post_id", Integer, ForeignKey("event_posts.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
)

event_hosts = Table(
    "event_hosts",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("event_post_id", Integer, ForeignKey("event_posts.id"), primary_key=True),
    Column("role", EnumType(HostRole), server_default=HostRole.owner.value, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())
)

 
class Users(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(200), nullable=False)
    last_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(550), nullable=False)
    dob: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    profile_photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), nullable=True)
    bio: Mapped[str] = mapped_column(String(280), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    posts: Mapped[list['Posts']] = relationship('Posts', back_populates='user')

    comments: Mapped[list['Comments']] = relationship('Comments', back_populates='user')

    following: Mapped[list['Users']] = relationship('Users', secondary=follows, primaryjoin=id == follows.c.follower_id, secondaryjoin=id == follows.c.followed_id, backref='followers')

    liked_posts: Mapped[list['Posts']] = relationship('Posts', secondary=post_likes, back_populates='liked_by')

    rsvps: Mapped[list['EventPosts']] = relationship('EventPosts', secondary=event_rsvps, back_populates='attendees')

    hosted_events: Mapped[list['EventPosts']] = relationship('EventPosts', secondary=event_hosts, back_populates='hosts')

    profile_photo: Mapped['Photos'] = relationship('Photos', primaryjoin='Users.profile_photo_id==Photos.id', foreign_keys='Users.profile_photo_id')

    photos: Mapped[list['Photos']] = relationship('Photos', back_populates='user', primaryjoin='Users.id==Photos.user_id', foreign_keys='Photos.user_id')


class Photos(Base):
    __tablename__ = 'photos'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped['Users'] = relationship('Users', back_populates='photos', primaryjoin='Photos.user_id==Users.id', foreign_keys='Photos.user_id')
    post: Mapped['Posts'] = relationship('Posts', back_populates='photos', primaryjoin='Photos.post_id==Posts.id', foreign_keys='Photos.post_id')

    def to_dict(self):
        return{
            'id': self.id,
            'filename': self.filename,
            'content_type': self.content_type,
            'upload_date': self.upload_date.isoformat()
        }

class Posts(Base):
    __tablename__ = 'posts'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    caption: Mapped[str] = mapped_column(String(1000), nullable=True)
    location: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped['Users'] = relationship('Users', back_populates='posts')

    comments: Mapped[list['Comments']] = relationship('Comments', back_populates='post')

    liked_by: Mapped[list['Users']] = relationship('Users', secondary=post_likes, back_populates='liked_posts')

    photos: Mapped[list['Photos']] = relationship('Photos', back_populates='post', primaryjoin='Posts.id==Photos.post_id', foreign_keys='Photos.post_id')

class Comments(Base):
    __tablename__ = 'comments'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey('posts.id'), nullable=False)
    comment: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped['Users'] = relationship('Users', back_populates='comments')
    post: Mapped['Posts'] = relationship('Posts', back_populates='comments')

class EventPosts(Base):
    __tablename__ = 'event_posts'

    id: Mapped[int] = mapped_column(primary_key=True)
    cover_photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    street_address: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(150), nullable=False)
    zipcode: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(200), nullable=False)

    hosts: Mapped[list['Users']] = relationship('Users', secondary=event_hosts, back_populates='hosted_events')
    attendees: Mapped[list['Users']] = relationship('Users', secondary=event_rsvps, back_populates='rsvps')
    cover_photo: Mapped['Photos'] = relationship('Photos', primaryjoin="EventPosts.cover_photo_id==Photos.id", foreign_keys='EventPosts.cover_photo_id')
    


