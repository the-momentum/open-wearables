from app.integrations.sqladmin.base_view import BaseAdminView
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserAdminView(
    BaseAdminView,
    model=User,
    create_schema=UserCreate,
    update_schema=UserUpdate,
    column={"searchable": ["username", "email"]},
):
    pass
