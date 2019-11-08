from functools import wraps

from flask import current_app
from flask_login import current_user


"""
========================================================
    A bunch of useful functions
========================================================
"""


def get_user_from_username(username):
    from app import models
    return models.User.query.filter(models.User.username == username).first()


def get_current_user():
    from app import auth, models
    from app.models import AnonymousUser
    if auth.username() == "":
        user = current_user
        if user.is_anonymous:
            user = AnonymousUser()
    else:
        user = models.User.verify_auth_token(auth.username())
        if not user:
            user = models.User.query.filter(models.User.username == auth.username()).first()
        if not user:
            user = AnonymousUser()

    return user


def make_error(status, title, details=None):
    from app import APIResponseFactory
    e = {"status": status, "title": title}
    if details:
        e["details"] = details
    return APIResponseFactory.make_response(status=status, errors=e)


def make_success(data, status=200):
    from app import APIResponseFactory
    return APIResponseFactory.make_response(status=status, data=data)


def make_403(details=None):
    return make_error(403, "Access forbidden", details)


def make_404(details=None):
    return make_error(404, "The resource does not exist", details)


def make_400(details=None):
    return make_error(400, "Error", details)


def make_409(details=None):
    return make_error(409, "Conflict with the current state of the target resource", details)


def make_200(data=None):
    if data is None:
        data = []
    return make_success(data)


def make_204():
    return make_success(204)


def forbid_if_another_teacher(app, wanted_teacher_id):
    user = app.get_current_user()
    if user.is_admin:
        return None
    if user.is_anonymous or not user.is_teacher or (wanted_teacher_id != user.id):
        return make_403("This resource is not available to other teachers")
    else:
        return None


def forbid_if_nor_teacher_nor_admin_and_wants_user_data(app, wanted_user_id):
    user = app.get_current_user()
    # if anonymous or mere student wants to read data of another student
    if user.is_anonymous or not (user.is_teacher or user.is_admin) and wanted_user_id is not None and int(wanted_user_id) != int(user.id):
        return make_403("You must be a teacher or an admin")
    else:
        return None


def forbid_if_nor_teacher_nor_admin(view_function):
    @wraps(view_function)
    def wrapped_f(*args, **kwargs):
        user = current_app.get_current_user()
        if user.is_anonymous or not (user.is_teacher or user.is_admin):
            return make_403("This resource is only available to teachers and admins")
        return view_function(*args, **kwargs)
    return wrapped_f


def is_closed(doc_id):
    from app.models import Document
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404()
    if doc.is_closed:
        return make_403()


def forbid_if_validation_step(doc_id, gte):
    from app.models import Document
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc and doc.validation_step >= gte:
        return make_403(details="Validation step")

