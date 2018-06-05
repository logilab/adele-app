from flask import url_for, request, redirect, current_app
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from app import db, auth
from app.api.response import APIResponseFactory
from app.api.routes import query_json_endpoint, api_bp
from app.api.translations.routes import get_reference_translation
from app.models import Transcription, User, Document, AlignmentTranslation, Translation, AlignmentDiscours, \
    SpeechPartType, Note, AlignmentImage, ImageZone

"""
===========================
    Transcriptions
===========================
"""


def get_reference_transcription(doc_id):
    """

    :param doc_id:
    :return:
    """
    transcription = None
    try:
        transcriptions = Transcription.query.filter(doc_id == Transcription.doc_id).all()
        for tr in transcriptions:
            user = User.query.filter(User.id == tr.user_id).first()
            if user.is_teacher:
                transcription = tr
                break
    except NoResultFound:
        pass

    return transcription


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/reference')
def api_documents_transcriptions_reference(api_version, doc_id):
    tr = get_reference_transcription(doc_id)
    if tr is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Transcription not found"
        })
    else:
        # filter notes
        notes = []
        for thn in tr.notes:
            if thn.note.user_id == tr.user_id:
                notes.append(thn)
        tr.notes = notes
        response = APIResponseFactory.make_response(data=tr.serialize())
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/users')
def api_documents_transcriptions_users(api_version, doc_id):
    try:
        transcriptions = Transcription.query.filter(Transcription.doc_id == doc_id).all()
        users = User.query.filter(User.id.in_(set([tr.user_id for tr in transcriptions]))).all()
        users = [{"id": user.id, "username": user.username} for user in users]
    except NoResultFound:
        users = []
    response = APIResponseFactory.make_response(data=users)
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions')
@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/from-user/<user_id>')
def api_documents_transcriptions(api_version, doc_id, user_id=None):
    response = None
    user = current_app.get_current_user()
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

    if response is None:

        if user is not None:
            # only teacher and admin can see everything
            if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != int(user.id):
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Access forbidden"
                })

        if response is None:
            if user_id is None:
                user_id = Transcription.user_id

            try:
                transcriptions = Transcription.query.filter(
                    Transcription.doc_id == doc_id,
                    Transcription.user_id == user_id
                ).all()

                if len(transcriptions) == 0:
                    raise NoResultFound

                response = APIResponseFactory.make_response(data=[tr.serialize() for tr in transcriptions])
            except NoResultFound:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": "Transcription not found"
                })

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions', methods=["POST"])
@auth.login_required
def api_post_documents_transcriptions(api_version, doc_id):
    """
    {
        "data":
            {
                "content" :  "My first transcription",   (mandatory)
                "username":  "Eleve1"                    (optionnal)
            }
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

            for tr in data:
                user = current_app.get_current_user()
                user_id = user.id
                # teachers and admins can put/post/delete on others behalf
                if (user.is_teacher or user.is_admin) and "username" in tr:
                    user = current_app.get_user_from_username(tr["username"])
                    if user is not None:
                        user_id = user.id

                # check that there's no transcription yet for this document/user
                existing_tr = Transcription.query.filter(
                    Transcription.user_id == user_id,
                    Transcription.doc_id == doc_id
                ).first()

                if existing_tr is not None:
                    response = APIResponseFactory.make_response(errors={
                        "status": 403,
                        "title": "Insert forbidden",
                    })
                    db.session.rollback()

                if response is None:
                    # get the transcription id max
                    try:
                        transcription_max_id = db.session.query(func.max(Transcription.id)).one()
                        transcription_max_id = transcription_max_id[0] + 1
                    except NoResultFound:
                        # it is the transcription for this user and this document
                        transcription_max_id = 1

                    new_transcription = Transcription(
                        id=transcription_max_id,
                        content=tr["content"],
                        doc_id=doc_id,
                        user_id=user_id
                    )

                    db.session.add(new_transcription)
                    created_users.add(user)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Cannot insert data", "details": str(e)
                })

            if response is None:
                created_data = []
                for usr in created_users:
                    json_obj = query_json_endpoint(
                        request,
                        url_for(
                            "api_bp.api_documents_transcriptions",
                            api_version=api_version,
                            doc_id=doc_id,
                            user_id=usr.id
                        ),
                        user=usr
                    )
                    if "data" in json_obj:
                        created_data.append(json_obj["data"])
                    elif "errors":
                        created_data.append(json_obj["errors"])

                response = APIResponseFactory.make_response(data=created_data)

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions', methods=["PUT"])
@auth.login_required
def api_put_documents_transcriptions(api_version, doc_id):
    """
    {
        "data": [
            {
                "content" :  "My first transcription",   (mandatory)
                "username":  "Eleve1"                    (optionnal)
            },
            {
                "content" :  "My first transcription",   (mandatory)
                "username":  "Eleve2"                    (optionnal)
            }
        ]
    }
    :param api_version:
    :param doc_id:
    :return:
    """
    data = request.get_json()
    response = None

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

            updated_users = set()
            user = current_app.get_current_user()
            user_id = user.id

            for tr in data:

                user = current_app.get_current_user()
                user_id = user.id

                # teachers and admins can put/post/delete on others behalf
                if (user.is_teacher or user.is_admin) and "username" in tr:
                    user = current_app.get_user_from_username(tr["username"])
                    if user is not None:
                        user_id = user.id
                elif "username" in tr:
                    usr = current_app.get_user_from_username(tr["username"])
                    if usr is not None and usr.id != user.id:
                        db.session.rollback()
                        response = APIResponseFactory.make_response(errors={
                            "status": 403, "title": "Access forbidden", "details": "Cannot update data"
                        })
                        break

                try:
                    # get the transcription to update
                    transcription = Transcription.query.filter(
                        Transcription.user_id == user_id,
                        Transcription.doc_id == doc_id
                    ).one()

                    transcription.content = tr["content"]
                    db.session.add(transcription)
                    # save which users to retriever later
                    updated_users.add(user)
                except NoResultFound:
                    response = APIResponseFactory.make_response(errors={
                        "status": 404,
                        "title": "Update forbidden",
                        "details": "Transcription not found"
                    })
                    break

            if response is None:
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Cannot update data", "details": str(e)
                    })

            if response is None:
                updated_data = []
                for usr in updated_users:
                    json_obj = query_json_endpoint(
                        request,
                        url_for(
                            "api_bp.api_documents_transcriptions",
                            api_version=api_version,
                            doc_id=doc_id,
                            user_id=user_id
                        ),
                        user=usr
                    )
                    updated_data.append(json_obj["data"])

                response = APIResponseFactory.make_response(data=updated_data)

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/from-user/<user_id>', methods=["DELETE"])
@auth.login_required
def api_delete_documents_transcriptions(api_version, doc_id, user_id):
    """
     :param api_version:
     :param doc_id:
     :return:
     """
    response = None

    try:
        doc = Document.query.filter(Document.id == doc_id).one()
    except NoResultFound:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Document {0} not found".format(doc_id)
        })

    user = current_app.get_current_user()
    if user is not None:
        if (not user.is_teacher and not user.is_admin) and int(user_id) != user.id:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })

    # delete transcriptions for the given user id
    if response is None:
        try:
            # bring the transcription to delete
            transcription = Transcription.query.filter(
                Transcription.user_id == user_id,
                Transcription.doc_id == doc_id
            ).one()
            db.session.delete(transcription)
        except NoResultFound:
            pass

        if response is None:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Cannot delete data", "details": str(e)
                })

        if response is None:
            response = APIResponseFactory.make_response(data=[])

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments')
@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/from-user/<user_id>')
def api_documents_transcriptions_alignments(api_version, doc_id, user_id=None):
    """
    If user_id is None: get the reference translation (if any) to find the alignment
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    user = current_app.get_current_user()
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })

    else:
        alignments = []
        if user is not None:
            if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != user.id:
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Access forbidden"
                })
        elif user_id is not None:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })
        # pick the reference translation if you are not logged
        if user is None:
            translation = get_reference_translation(doc_id)
            alignments = AlignmentTranslation.query.filter(
                AlignmentTranslation.transcription_id == transcription.id,
                AlignmentTranslation.translation_id == translation.id
            ).all()
        else:
            json_obj = query_json_endpoint(
                request,
                url_for(
                    "api_bp.api_documents_translations",
                    api_version=api_version,
                    doc_id=doc_id,
                    user_id=user_id
                ),
                user=user
            )

            if "data" not in json_obj:
                response = APIResponseFactory.make_response(errors=json_obj["errors"])
            else:
                translation = json_obj["data"]

                alignments = AlignmentTranslation.query.filter(
                    AlignmentTranslation.transcription_id == transcription.id,
                    AlignmentTranslation.translation_id == translation["id"]
                ).all()

        if response is None:
            ptrs = [(a.ptr_transcription_start, a.ptr_transcription_end,
                     a.ptr_translation_start, a.ptr_translation_end)
                    for a in alignments]

            response = APIResponseFactory.make_response(data=ptrs)

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/reference')
def api_documents_transcriptions_alignments_reference(api_version, doc_id):
    """
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })

    translation = get_reference_translation(doc_id)

    if translation is None and response is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference translation not found"
        })
    else:
        alignments = AlignmentTranslation.query.filter(
            AlignmentTranslation.transcription_id == transcription.id,
            AlignmentTranslation.translation_id == translation.id
        ).all()

        ptrs = [
            (a.ptr_transcription_start, a.ptr_transcription_end, a.ptr_translation_start, a.ptr_translation_end)
            for a in alignments
        ]

        response = APIResponseFactory.make_response(data=ptrs)

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/from-user/<user_id>', methods=['DELETE'])
@auth.login_required
def api_delete_documents_transcriptions_alignments(api_version, doc_id, user_id):
    """
        If user_id is None: get the reference translation (if any) to find the alignment
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None
    user = current_app.get_current_user()
    if user is None or (not user.is_teacher and not user.is_admin) and int(user_id) != user.id:
        response = APIResponseFactory.make_response(errors={
            "status": 403, "title": "Access forbidden"
        })

    if response is None:
        transcription = get_reference_transcription(doc_id)
        if transcription is None:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Reference transcription not found"
            })

        translation = Translation.query.filter(
            Translation.doc_id == doc_id,
            Translation.user_id == user_id
        ).one()

        if response is None:
            try:
                alignments = AlignmentTranslation.query.filter(
                    AlignmentTranslation.transcription_id == transcription.id,
                    AlignmentTranslation.translation_id == translation.id
                ).all()

                for al in alignments:
                    db.session.delete(al)

            except NoResultFound as e:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": str(e)
                })
                db.session.rollback()

            if response is None:
                try:
                    db.session.commit()
                    response = APIResponseFactory.make_response()
                except Exception as e:
                    db.session.rollback()
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Cannot delete data", "details": str(e)
                    })

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments', methods=['POST'])
@auth.login_required
def api_post_documents_transcriptions_alignments(api_version, doc_id):
    """
        {
            "data": {
                "username" : "Eleve1",
                "ptr_list" : [
                    [...],
                    [...]
                ]
            }
        }

        If user_id is None: get the reference translation (if any) to find the alignment
        :param api_version:
        :param doc_id:
        :param user_id:
        :return:
        """
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })
    else:
        if response is None:
            data = request.get_json()
            if "data" in data and "ptr_list" in data["data"]:
                data = data["data"]

                user = current_app.get_current_user()
                user_id = user.id

                if not (user.is_teacher or user.is_admin) and "username" in data and data["username"] != user.username:
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Access forbidden"
                    })

                if response is None:
                    # teachers and admins can put/post/delete on others behalf
                    if (user.is_teacher or user.is_admin) and "username" in data:
                        user = current_app.get_user_from_username(data["username"])
                        if user is not None:
                            user_id = user.id

                    json_obj = query_json_endpoint(
                        request,
                        url_for(
                            "api_bp.api_documents_translations",
                            api_version=api_version,
                            doc_id=doc_id,
                            user_id=user_id
                        ),
                        user=user
                    )

                    if "data" not in json_obj:
                        response = APIResponseFactory.make_response(errors=json_obj["errors"])
                        translation = None
                    else:
                        translation = json_obj["data"]

                        # let's make the new alignments from the data
                    if translation is not None and response is None:

                        if not isinstance(data["ptr_list"], list):
                            data = [data["ptr_list"]]
                        else:
                            data = data["ptr_list"]

                        # DELETE the old data
                        for old_al in AlignmentTranslation.query.filter(
                                AlignmentTranslation.transcription_id == transcription.id,
                                AlignmentTranslation.translation_id == translation["id"]
                        ).all():
                            db.session.delete(old_al)

                        if response is None:
                            for (ptr_transcription_start, ptr_transcription_end,
                                 ptr_translation_start, ptr_translation_end) in data:
                                new_al = AlignmentTranslation(
                                    transcription_id=transcription.id, translation_id=translation["id"],
                                    ptr_transcription_start=ptr_transcription_start,
                                    ptr_transcription_end=ptr_transcription_end,
                                    ptr_translation_start=ptr_translation_start,
                                    ptr_translation_end=ptr_translation_end
                                )
                                db.session.add(new_al)

                            try:
                                db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                response = APIResponseFactory.make_response(errors={
                                    "status": 403, "title": "Cannot insert data", "details": str(e)
                                })

                            if response is None:
                                json_obj = query_json_endpoint(
                                    request,
                                    url_for(
                                        "api_bp.api_documents_transcriptions_alignments",
                                        api_version=api_version,
                                        doc_id=doc_id,
                                        user_id=user_id
                                    ),
                                    user=user
                                )
                                if "data" in json_obj:
                                    response = APIResponseFactory.make_response(data=json_obj["data"])
                                else:
                                    response = APIResponseFactory.make_response(data=json_obj["errors"])
        else:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Data is malformed"
            })
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/discours')
@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/discours/from-user/<user_id>')
def api_documents_transcriptions_alignments_discours(api_version, doc_id, user_id=None):
    """
    If user_id is None: get the reference translation (if any) to find the alignment
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    user = current_app.get_current_user()
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })

    else:
        if user is not None:
            if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != user.id:
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Access forbidden"
                })
        elif user_id is not None:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })

        if response is None:

            if user is None:
                user_id = transcription.user_id

            if user_id is None:
                if not (user.is_teacher or user.is_admin):
                    user_id = user.id
                else:
                    user_id = AlignmentDiscours.user_id

            alignments = AlignmentDiscours.query.filter(
                AlignmentDiscours.transcription_id == transcription.id,
                AlignmentDiscours.user_id == user_id
            ).all()

            response = APIResponseFactory.make_response(data=[al.serialize() for al in alignments])

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/discours', methods=['POST'])
@auth.login_required
def api_post_documents_transcriptions_alignments_discours(api_version, doc_id):
    """
        {
            "data": {
                "username" : "Eleve1",
                "speech_parts" : [
                    {
                        "type_id" : 1,
                        "ptr_start": 1,
                        "ptr_end": 20
                    },
                    {
                        "type_id" : 2,
                        "ptr_start": 21,
                        "ptr_end": 450,
                        "note_id": 33
                    }
                ]
            }
        }

        If user_id is None: get the reference translation (if any) to find the alignment
        :param api_version:
        :param doc_id:
        :return:
        """
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })
    else:
        if response is None:
            data = request.get_json()
            if "data" in data and "speech_parts" in data["data"]:
                data = data["data"]

                user = current_app.get_current_user()
                user_id = user.id

                if not (user.is_teacher or user.is_admin) and "username" in data and data["username"] != user.username:
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Access forbidden"
                    })

                if response is None:
                    # teachers and admins can put/post/delete on others behalf
                    if (user.is_teacher or user.is_admin) and "username" in data:
                        user = current_app.get_user_from_username(data["username"])
                        if user is not None:
                            user_id = user.id

                    # let's make the new alignments from the data
                    if response is None:

                        if not isinstance(data["speech_parts"], list):
                            data = [data["speech_parts"]]
                        else:
                            data = data["speech_parts"]

                        # DELETE the old data
                        for old_al in AlignmentDiscours.query.filter(
                                AlignmentDiscours.transcription_id == transcription.id,
                                AlignmentDiscours.user_id == user_id
                        ).all():
                            db.session.delete(old_al)

                        if response is None:
                            try:
                                for speech_part in data:
                                    if "note_id" in speech_part:
                                        note_id = int(speech_part["note_id"])
                                        Note.query.filter(Note.id == note_id).one()
                                    else:
                                        note_id = None

                                    part_type = SpeechPartType.query.filter(
                                        SpeechPartType.id == int(speech_part["type_id"])
                                    ).one()

                                    new_al = AlignmentDiscours(
                                        transcription_id=transcription.id,
                                        speech_part_type_id=part_type.id,
                                        user_id=user_id,
                                        ptr_start=speech_part["ptr_start"],
                                        ptr_end=speech_part["ptr_end"],
                                        note_id=note_id
                                    )
                                    db.session.add(new_al)

                                db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                response = APIResponseFactory.make_response(errors={
                                    "status": 403, "title": "Cannot insert data", "details": str(e)
                                })

                            if response is None:
                                json_obj = query_json_endpoint(
                                    request,
                                    url_for(
                                        "api_bp.api_documents_transcriptions_alignments_discours",
                                        api_version=api_version,
                                        doc_id=doc_id,
                                        user_id=user_id
                                    ),
                                    user=user
                                )
                                if "data" in json_obj:
                                    response = APIResponseFactory.make_response(data=json_obj["data"])
                                else:
                                    response = APIResponseFactory.make_response(data=json_obj["errors"])
        else:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Data is malformed"
            })
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/discours/reference')
def api_documents_transcriptions_alignments_discours_reference(api_version, doc_id):
    """
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None
    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })

    if response is None:
        alignments = AlignmentDiscours.query.filter(
             AlignmentDiscours.transcription_id == transcription.id,
             AlignmentDiscours.user_id == transcription.user_id
        ).all()

        response = APIResponseFactory.make_response(data=[al.serialize() for al in alignments])

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/discours/from-user/<user_id>', methods=['DELETE'])
@auth.login_required
def api_delete_documents_transcriptions_alignments_discours(api_version, doc_id, user_id=None):
    """
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None
    user = current_app.get_current_user()
    if not (user.is_teacher or user.is_admin) and int(user_id) != user.id:
        response = APIResponseFactory.make_response(errors={
            "status": 403, "title": "Access forbidden"
        })

    if response is None:
        transcription = get_reference_transcription(doc_id)
        if transcription is None:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Reference transcription not found"
            })

        if response is None:
            try:
                alignments = AlignmentDiscours.query.filter(
                    AlignmentDiscours.transcription_id == transcription.id,
                    AlignmentDiscours.user_id == user_id
                ).all()

                for al in alignments:
                    db.session.delete(al)

            except NoResultFound as e:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": str(e)
                })
                db.session.rollback()

            if response is None:
                try:
                    db.session.commit()
                    response = APIResponseFactory.make_response()
                except Exception as e:
                    db.session.rollback()
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Cannot delete data", "details": str(e)
                    })

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/images')
@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/images/from-user/<user_id>')
def api_documents_transcriptions_alignments_images(api_version, doc_id, user_id=None):
    """
    If user_id is None: get the reference translation (if any) to find the alignment
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    user = current_app.get_current_user()
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })

    else:
        if user is not None:
            if (not user.is_teacher and not user.is_admin) and user_id is not None and int(user_id) != user.id:
                response = APIResponseFactory.make_response(errors={
                    "status": 403, "title": "Access forbidden"
                })
        elif user_id is not None:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Access forbidden"
            })

        if response is None:

            if user is None:
                user_id = transcription.user_id

            if user_id is None:
                if not (user.is_teacher or user.is_admin):
                    user_id = user.id
                else:
                    user_id = AlignmentImage.user_id
            else:
                user_id = int(user_id)

            alignments = AlignmentImage.query.filter(
                AlignmentImage.transcription_id == transcription.id,
                AlignmentImage.user_id == user_id
            ).all()

            response = APIResponseFactory.make_response(data=[al.serialize() for al in alignments])

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/images/reference')
def api_documents_transcriptions_alignments_images_reference(api_version, doc_id):
    """
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None
    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })

    if response is None:
        alignments = AlignmentImage.query.filter(
            AlignmentImage.transcription_id == transcription.id,
            AlignmentImage.user_id == transcription.user_id
        ).all()

        response = APIResponseFactory.make_response(data=[al.serialize() for al in alignments])

    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/images', methods=['POST'])
@auth.login_required
def api_post_documents_transcriptions_alignments_images(api_version, doc_id):
    """
        {
            "data": {
                "username" : "Eleve1",
                "manifest_url" :  "http://193.48.42.68/adele/iiif/manifests/man20.json",
                "img_id" : "http://193.48.42.68/loris/adele/dossiers/20.jpg/full/full/0/default.jpg",
                "alignments" : [
                    {
                        "zone_id" : 1,
                        "ptr_start": 1,
                        "ptr_end": 20
                    },
                    {
                        "zone_id" : 2,
                        "ptr_start": 21,
                        "ptr_end": 450
                    }
                ]
            }
        }

        :param api_version:
        :param doc_id:
        :return:
        """
    response = None

    transcription = get_reference_transcription(doc_id)

    if transcription is None:
        response = APIResponseFactory.make_response(errors={
            "status": 404, "title": "Reference transcription not found"
        })
    else:
        if response is None:
            data = request.get_json()
            if "data" in data and "alignments" in data["data"]:
                data = data["data"]

                user = current_app.get_current_user()
                user_id = user.id

                if not (user.is_teacher or user.is_admin) and "username" in data and data["username"] != user.username:
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Access forbidden"
                    })

                if not("manifest_url" in data and "img_id" in data):
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Data is malformed"
                    })

                if response is None:
                    # teachers and admins can put/post/delete on others behalf
                    if (user.is_teacher or user.is_admin) and "username" in data:
                        user = current_app.get_user_from_username(data["username"])
                        if user is not None:
                            user_id = user.id

                    # let's make the new alignments from the data
                    if response is None:

                        if not isinstance(data["alignments"], list):
                            alignments = [data["alignments"]]
                        else:
                            alignments = data["alignments"]

                        # DELETE the old data
                        for old_al in AlignmentImage.query.filter(
                            AlignmentImage.transcription_id == transcription.id,
                            AlignmentImage.user_id == int(user_id),
                            AlignmentImage.manifest_url == data["manifest_url"],
                            AlignmentImage.img_id == data["img_id"]
                        ).all():
                            db.session.delete(old_al)

                        if response is None:
                            try:
                                for alignment in alignments:

                                    zone = ImageZone.query.filter(
                                        ImageZone.zone_id == int(alignment["zone_id"]),
                                        ImageZone.manifest_url == data["manifest_url"],
                                        ImageZone.user_id == int(user_id),
                                        ImageZone.img_id == data["img_id"]
                                    ).one()

                                    new_al = AlignmentImage(
                                        transcription_id=transcription.id,
                                        user_id=user_id,
                                        manifest_url=data["manifest_url"],
                                        img_id=data["img_id"],
                                        zone_id=zone.zone_id,
                                        ptr_transcription_start=alignment["ptr_start"],
                                        ptr_transcription_end=alignment["ptr_end"]
                                    )
                                    db.session.add(new_al)

                                db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                response = APIResponseFactory.make_response(errors={
                                    "status": 403, "title": "Cannot insert data", "details": str(e)
                                })

                            if response is None:
                                json_obj = query_json_endpoint(
                                    request,
                                    url_for(
                                        "api_bp.api_documents_transcriptions_alignments_images",
                                        api_version=api_version,
                                        doc_id=doc_id,
                                        user_id=user_id
                                    ),
                                    user=user
                                )
                                if "data" in json_obj:
                                    response = APIResponseFactory.make_response(data=json_obj["data"])
                                else:
                                    response = APIResponseFactory.make_response(data=json_obj["errors"])
        else:
            response = APIResponseFactory.make_response(errors={
                "status": 403, "title": "Data is malformed"
            })
    return APIResponseFactory.jsonify(response)


@api_bp.route('/api/<api_version>/documents/<doc_id>/transcriptions/alignments/images/from-user/<user_id>', methods=['DELETE'])
@auth.login_required
def api_delete_documents_transcriptions_alignments_images(api_version, doc_id, user_id=None):
    """
    :param api_version:
    :param doc_id:
    :param user_id:
    :return:
    """
    response = None
    user = current_app.get_current_user()
    if not (user.is_teacher or user.is_admin) and int(user_id) != user.id:
        response = APIResponseFactory.make_response(errors={
            "status": 403, "title": "Access forbidden"
        })

    if response is None:
        transcription = get_reference_transcription(doc_id)
        if transcription is None:
            response = APIResponseFactory.make_response(errors={
                "status": 404, "title": "Reference transcription not found"
            })

        if response is None:
            try:
                alignments = AlignmentImage.query.filter(
                    AlignmentImage.transcription_id == transcription.id,
                    AlignmentImage.user_id == user_id
                ).all()

                for al in alignments:
                    db.session.delete(al)

            except NoResultFound as e:
                response = APIResponseFactory.make_response(errors={
                    "status": 404, "title": str(e)
                })
                db.session.rollback()

            if response is None:
                try:
                    db.session.commit()
                    response = APIResponseFactory.make_response()
                except Exception as e:
                    db.session.rollback()
                    response = APIResponseFactory.make_response(errors={
                        "status": 403, "title": "Cannot delete data", "details": str(e)
                    })

    return APIResponseFactory.jsonify(response)

