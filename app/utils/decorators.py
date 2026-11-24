from functools import wraps

from flask import session, redirect, url_for
from app.repositories.user_repository import UserRepository


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(
                url_for("auth.login")
            )

        user = UserRepository().find_by_id(session['user_id'])
        if not user or not user.get('active', True) or user.get('role') != session.get('user_role'):
            session.clear()
            return redirect(url_for('auth.login'))
        return function(*args, **kwargs)

    return wrapper