from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.errors import ConflictError, NotFoundError
from app.extensions import db
from app.models import User
from app.services.validators import validate_user_payload


def _base_query(search=None):
    query = select(User).order_by(User.id)
    if search:
        query = query.where(
            or_(
                User.name.contains(search, autoescape=True),
                User.email.contains(search, autoescape=True),
            )
        )
    return query


def list_users(search=None, page=None, limit=None):
    query = _base_query(search)

    if page is None and limit is None:
        return db.session.scalars(query).all(), None

    result = db.paginate(query, page=page, per_page=limit, error_out=False, count=True)
    pagination = {
        "page": result.page,
        "limit": result.per_page,
        "total": result.total,
        "pages": result.pages,
    }
    return result.items, pagination


def get_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def create_user(payload):
    data = validate_user_payload(payload)

    if db.session.scalar(select(User.id).where(User.email == data["email"])):
        raise ConflictError("Email already exists")

    user = User(**data)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ConflictError("Email already exists")
    return user
