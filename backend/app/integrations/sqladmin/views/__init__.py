from sqladmin import Admin

from .user import UserAdminView


def add_admin_views(admin: Admin) -> None:
    views = [
        UserAdminView,
    ]
    for view in views:
        admin.add_view(view)