from flask import request, redirect, url_for
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from app import get_current_user, auth, get_user_from_username, db
from app.api.response import APIResponseFactory
from app.api.routes import api_bp, query_json_endpoint
from app.api.transcriptions.routes import get_reference_transcription
from app.api.translations.routes import get_reference_translation
from app.models import Transcription, Commentary, Translation, Note, NoteType, Document, TranslationHasNote, \
    TranscriptionHasNote


"""
===========================
    Notes
===========================
"""


@api_bp.route('/api/<api_version>/notes', methods=['GET', 'POST'])
def api_add_note(api_version):
    note_data = request.get_json()
    # note = Note()
    # dump(data)
    return APIResponseFactory.jsonify({
        'note_data': note_data
    })


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/reference/notes')
def api_documents_transcriptions_reference_notes(api_version, doc_id):
    tr = get_reference_transcription(doc_id)
    if tr is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Transcription not found"
        })
    else:
        response = APIResponseFactory.make_response(data=[
            thn.note.serialize() for thn in tr.notes if thn.note.user_id == tr.user_id
        ])
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/translations/reference/notes')
def api_documents_translations_reference_notes(api_version, doc_id):
    tr = get_reference_translation(doc_id)
    if tr is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Translation not found"
        })
    else:
        response = APIResponseFactory.make_response(data=[
            thn.note.serialize() for thn in tr.notes if thn.note.user_id == tr.user_id
        ])
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/commentaries/reference/notes')
def api_documents_commentaries_reference_notes(api_version, doc_id):
    tr = get_reference_transcription(doc_id)

    if tr is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Transcription not found"
        })
    else:
        notes = []
        commentaries = Commentary.query.filter(Commentary.doc_id == doc_id, Commentary.user_id == tr.user_id).all()
        for c in commentaries:
            notes.extend(c.notes)

        response = APIResponseFactory.make_response(data=[n.serialize() for n in notes])
    return APIResponseFactory.jsonify(response)


@api_bp.route("/api/<api_version>/documents/<doc_id>/transcriptions/notes")
@api_bp.route("/api/<api_version>/documents/<doc_id>/transcriptions/notes/<note_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/transcriptions/notes/from-user/<user_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/transcriptions/notes/<note_id>/from-user/<user_id>")
def api_documents_transcriptions_notes(api_version, doc_id, note_id=None, user_id=None):
    # sélectionner la liste des notes de transcription d'un utilisateur pour un doc
    """

    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None

    user = get_current_user()
    if user is None and user_id is not None:
        response = APIResponseFactory.make_response(errors={
            "status": 403, "title": "Access forbidden"
        })
    elif user is None:
        tr = get_reference_transcription(doc_id)
        if tr is None:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Transcription not found"
            })
        else:
            user_id = tr.user_id
    else:
        # user_id is None and user is not None
        if not user.is_teacher and not user.is_admin:
            user_id = user.id

    # only teacher and admin can see everything
    if user is not None:
        if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != user.id:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })

    if response is None:

        transcriptions = []
        try:
            if user_id is None:
                transcriptions = Transcription.query.filter(Transcription.doc_id == doc_id).all()
            else:
                user_id = int(user_id)
                transcriptions = Transcription.query.filter(Transcription.doc_id == doc_id, Transcription.user_id == user_id).all()
        except NoResultFound:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Transcription not found"
            })

        notes = []
        for tr in transcriptions:
            for thn in tr.notes:
                if user_id is None:
                    if note_id is None:
                        notes.append(thn.note)
                    elif int(note_id) == thn.note.id:
                        notes.append(thn.note)
                elif thn.note.user_id == user_id or (user.is_teacher or user.is_admin):
                    if note_id is None:
                        notes.append(thn.note)
                    elif int(note_id) == thn.note.id:
                        notes.append(thn.note)

        if response is None:
            if len(notes) == 0:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": "Notes not found"
                })
            else:
                response = APIResponseFactory.make_response(data=[note.serialize() for note in notes])

    return APIResponseFactory.jsonify(response)


@api_bp.route("/api/<api_version>/documents/<doc_id>/translations/notes")
@api_bp.route("/api/<api_version>/documents/<doc_id>/translations/notes/<note_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/translations/notes/from-user/<user_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/translations/notes/<note_id>/from-user/<user_id>")
def api_documents_translations_notes(api_version, doc_id, note_id=None, user_id=None):
    # sélectionner la liste des notes de translation d'un utilisateur pour un doc
    """

    :param note_id:
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None

    user = get_current_user()
    if user is None and user_id is not None:
        response = APIResponseFactory.make_response(errors={
            "status": 403, "title": "Access forbidden"
        })
    elif user is None:
        tr = get_reference_translation(doc_id)
        if tr is None:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Translation not found"
            })
        else:
            user_id = tr.user_id
    else:
        # user_id is None and user is not None
        if not user.is_teacher and not user.is_admin:
            user_id = user.id

    # only teacher and admin can see everything
    if user is not None:
        if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != user.id:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })

    if response is None:

        translations = []
        try:
            if user_id is None:
                translations = Translation.query.filter(Translation.doc_id == doc_id).all()
            else:
                user_id = int(user_id)
                translations = Translation.query.filter(Translation.doc_id == doc_id, Translation.user_id == user_id).all()
        except NoResultFound:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Translation not found"
            })

        notes = []
        for tr in translations:
            for thn in tr.notes:
                if user_id is None:
                    if note_id is None:
                        notes.append(thn.note)
                    elif int(note_id) == thn.note.id:
                        notes.append(thn.note)
                elif thn.note.user_id == user_id or (user.is_teacher or user.is_admin):
                    if note_id is None:
                        notes.append(thn.note)
                    elif int(note_id) == thn.note.id:
                        notes.append(thn.note)

        if response is None:
            if len(notes) == 0:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": "Notes not found"
                })
            else:
                response = APIResponseFactory.make_response(data=[note.serialize() for note in notes])

    return APIResponseFactory.jsonify(response)


@api_bp.route("/api/<api_version>/documents/<doc_id>/commentaries/notes")
@api_bp.route("/api/<api_version>/documents/<doc_id>/commentaries/notes/<note_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/commentaries/notes/from-user/<user_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/commentaries/notes/<note_id>/from-user/<user_id>")
def api_documents_commentaries_notes(api_version, doc_id, note_id=None, user_id=None):
    # sélectionner la liste des notes de commentary d'un utilisateur pour un doc
    """

    :param note_id:
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None

    user = get_current_user()
    if user is None and user_id is not None:
        response = APIResponseFactory.make_response(errors={
            "status": 403, "title": "Access forbidden"
        })
    elif user is None:
        tr = get_reference_transcription(doc_id)
        if tr is None:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Commentary not found"
            })
        else:
            user_id = tr.user_id
    else:
        # user_id is None and user is not None
        if not user.is_teacher and not user.is_admin:
            user_id = user.id

    # only teacher and admin can see everything
    if user is not None:
        if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != user.id:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })

    if response is None:

        commentaries = []
        try:
            if user_id is None:
                commentaries = Commentary.query.filter(Commentary.doc_id == doc_id).all()
            else:
                user_id = int(user_id)
                commentaries = Commentary.query.filter(Commentary.doc_id == doc_id, Commentary.user_id == user_id).all()
        except NoResultFound:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Commentary not found"
            })

        notes = []
        for c in commentaries:
            if user_id is None:
                if note_id is None:
                    notes.append(c.note)
                elif int(note_id) == c.note.id:
                     notes.append(c.note)
            elif c.note.user_id == user_id or (user.is_teacher or user.is_admin):
                if note_id is None:
                    notes.append(c.note)
                elif int(note_id) == c.note.id:
                    notes.append(c.note)

        if response is None:
            if len(notes) == 0:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": "Notes not found"
                })
            else:
                response = APIResponseFactory.make_response(data=[note.serialize() for note in notes])

    return APIResponseFactory.jsonify(response)


@api_bp.route("/api/<api_version>/documents/<doc_id>/notes")
@api_bp.route("/api/<api_version>/documents/<doc_id>/notes/<note_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/notes/from-user/<user_id>")
@api_bp.route("/api/<api_version>/documents/<doc_id>/notes/<note_id>/from-user/<user_id>")
def api_documents_notes(api_version, doc_id, note_id=None, user_id=None):

    user = get_current_user()
    args = {
        "api_version": api_version,
        "doc_id" : doc_id,
        "user_id" : user_id,
        "note_id": note_id
    }

    data = []
    errors = []

    transcriptions_notes = query_json_endpoint(
        request,
        url_for( "api_bp.api_documents_transcriptions_notes", **args), user=user
    )
    if "data" in transcriptions_notes:
        data.extend(transcriptions_notes["data"])
    else:
        errors.append(transcriptions_notes["errors"])

    translations_notes = query_json_endpoint(
        request,
        url_for( "api_bp.api_documents_translations_notes", **args), user=user
    )
    if "data" in translations_notes:
        data.extend(translations_notes["data"])
    else:
        errors.append(translations_notes["errors"])

    commentaries_notes = query_json_endpoint(
        request,
        url_for( "api_bp.api_documents_commentaries_notes", **args), user=user
    )

    if "data" in commentaries_notes:
        data.extend(commentaries_notes["data"])
    else:
        errors.append(commentaries_notes["errors"])

    if len(errors) != 0 and len(data) == 0:
        response = APIResponseFactory.make_response(errors=errors)
    else:
        response = APIResponseFactory.make_response(data=data)

    return APIResponseFactory.jsonify(response)


def make_note_from_data(user_id, data, note_id, src=None):
    """
    :param note_id:
    :param src:
    :param user_id:
    :param data:
    :return:
    """
    if isinstance(src, Transcription):
        # TODO: todo gérer erreur
        note_type = NoteType.query.filter(NoteType.id == data["note_type"]).first()
        note = Note(id=note_id, user_id=user_id, content=data["content"], type_id=note_type.id, note_type=note_type)
        transcription_has_note = TranscriptionHasNote()
        transcription_has_note.transcription = src
        transcription_has_note.transcription_id = src.id
        transcription_has_note.note = note
        transcription_has_note.ptr_start = data["ptr_start"]
        transcription_has_note.ptr_end = data["ptr_end"]
        note.transcription = [transcription_has_note]
    else:
        raise NotImplementedError

    return note


@api_bp.route("/api/<api_version>/documents/<doc_id>/transcriptions/notes", methods=["POST"])
@auth.login_required
def api_post_documents_transcription_notes(api_version, doc_id):
    """
     {
        "data": [
                {
                    "username": "Eleve1" (optionnal),
                    "note_type": 1,
                    "content": "My first transcription note",
                    "ptr_start": 1,
                    "ptr_end": 80
                },
                {
                    "username": "Eleve1" (optionnal),
                    "note_type": 1,
                    "content": "My second transcription note",
                    "ptr_start": 80,
                    "ptr_end": 96
                }
        ]
    }
    :param api_version:
    :param doc_id:
    :return:
    """

    data = request.get_json()
    response = None
    created_users = set()

    try:
        doc = Document.query.filter(Document.id == doc_id).one()
    except NoResultFound:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Document {0} not found".format(doc_id)
        })

    if "data" in data and response is None:
        data = data["data"]

        if not isinstance(data, list):
            data = [data]

        if response is None:
            user = get_current_user()
            # local note id offset
            nb = 0
            # get the transcription id max
            try:
                note_max_id = db.session.query(func.max(Note.id)).one()
                note_max_id = note_max_id[0] + 1
            except NoResultFound:
                # it is the transcription for this user and this document
                note_max_id = 1

            for n_data in data:
                # user = get_current_user()
                user_id = user.id
                # teachers and admins can put/post/delete on others behalf
                if (user.is_teacher or user.is_admin) and "username" in n_data:
                    usr = get_user_from_username(n_data["username"])
                    if usr is not None:
                        user_id = usr.id

                # on wich transcription should the note be attached ?
                if (user.is_teacher or user.is_admin) and "transcription_username" in n_data:
                    tr_usr = get_user_from_username(n_data["transcription_username"])
                else:
                    tr_usr = user
                src = Transcription.query.filter(Transcription.user_id == tr_usr.id, Transcription.doc_id == doc_id).first()

                new_note = make_note_from_data(user_id, n_data, note_max_id + nb + 1, src)
                if new_note is not None:
                    db.session.add(new_note)
                    created_users.add((new_note.user_id, new_note.id, tr_usr))
                    # move local note id offset
                    nb += 1
                else:
                    raise NotImplementedError

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Cannot insert data", "details": str(e)
                })

            if response is None:
                created_data = []
                for note_user_id, note_id, tr_usr in created_users:
                    json_obj = query_json_endpoint(
                        request,
                        url_for(
                            "api_bp.api_documents_transcriptions_notes",
                            api_version=api_version,
                            doc_id=doc_id,
                            user_id=note_user_id,
                            note_id=note_id
                        ),
                        user=user
                    )
                    created_data.append(json_obj["data"])

                response = APIResponseFactory.make_response(data=created_data)

    return APIResponseFactory.jsonify(response)


@api_bp.route("/api/<api_version>/note-types")
def api_note_types(api_version):
    """

    :param api_version:
    :return:
    """
    try:
        note_types = NoteType.query.all()
        response = APIResponseFactory.make_response(data=[nt.serialize() for nt in note_types])
    except NoResultFound:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Types de note introuvables"
        })
    return APIResponseFactory.jsonify(response)
