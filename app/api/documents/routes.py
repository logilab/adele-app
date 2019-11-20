import datetime
from urllib.request import build_opener

from flask import request,  current_app
from flask_jwt_extended import jwt_required

from app import auth, db
from app.api.routes import api_bp, json_loads
from app.models import Document, Institution, Editor, Country, District, ActeType, Language, Tradition, Whitelist, \
    ImageUrl, Image, VALIDATION_TRANSCRIPTION, VALIDATION_NONE, get_validation_step_label, VALIDATIONS_STEPS_LABELS
from app.utils import make_404, make_200, forbid_if_nor_teacher_nor_admin_and_wants_user_data, make_400, \
    forbid_if_nor_teacher_nor_admin, make_204, make_409, forbid_if_another_teacher

"""
===========================
    Document
===========================
"""


@api_bp.route('/api/<api_version>/documents/<doc_id>')
def api_documents(api_version, doc_id):
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc:
        return make_200(doc.serialize())
    else:
        return make_404("Document {0} not found".format(doc_id))


@api_bp.route('/api/<api_version>/documents/<doc_id>/publish')
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_documents_publish(api_version, doc_id):
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404()

    is_another_teacher = forbid_if_another_teacher(current_app, doc.user_id)
    if is_another_teacher:
        return is_another_teacher

    try:
        doc.is_published = True
        db.session.commit()
        return make_200(data=doc.serialize())
    except Exception as e:
        return make_400(str(e))


@api_bp.route('/api/<api_version>/documents/<doc_id>/unpublish')
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_documents_unpublish(api_version, doc_id):
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404()

    is_another_teacher = forbid_if_another_teacher(current_app, doc.user_id)
    if is_another_teacher:
        return is_another_teacher
    try:
        doc.is_published = False
        db.session.commit()
        return make_200(data=doc.serialize())
    except Exception as e:
        return make_400(str(e))


@api_bp.route('/api/<api_version>/documents')
def api_documents_id_list(api_version):
    docs = Document.query.all()
    return make_200(data=[doc.serialize() for doc in docs])


@api_bp.route('/api/<api_version>/documents', methods=['POST'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_post_documents(api_version):
    data = request.get_json()
    if "data" in data:
        data = data["data"]

    tmp_doc = {
        "title": "Sans titre"
    }
    for key in ("title", "subtitle", "argument", "pressmark",
                "creation", "creation_lab", "copy_year", "copy_cent"):
        if key in data:
            tmp_doc[key] = data[key]

    if "institution_id" in data:
        tmp_doc["institution"] = Institution.query.filter(Institution.id == data["institution_id"]).first()

    if "editor_id" in data:
        if not isinstance(data["editor_id"], list):
            data["editor_id"] = [data["editor_id"]]
        tmp_doc["editors"] = Editor.query.filter(Editor.id.in_(data["editor_id"])).all()

    if "country_id" in data:
        if not isinstance(data["country_id"], list):
            data["country_id"] = [data["country_id"]]
        tmp_doc["countries"] = Country.query.filter(Country.id.in_(data["country_id"])).all()

    if "district_id" in data:
        if not isinstance(data["district_id"], list):
            data["district_id"] = [data["district_id"]]
        tmp_doc["districts"] = District.query.filter(District.id.in_(data["district_id"])).all()

    if "acte_type_id" in data:
        if not isinstance(data["acte_type_id"], list):
            data["acte_type_id"] = [data["acte_type_id"]]
        tmp_doc["acte_types"] = ActeType.query.filter(ActeType.id.in_(data["acte_type_id"])).all()

    if "language_code" in data:
        if not isinstance(data["language_code"], list):
            data["language_code"] = [data["language_code"]]
        tmp_doc["languages"] = Language.query.filter(Language.code.in_(data["language_code"])).all()

    if "tradition_id" in data:
        if not isinstance(data["tradition_id"], list):
            data["tradition_id"] = [data["tradition_id"]]
        tmp_doc["traditions"] = Tradition.query.filter(Tradition.id.in_(data["tradition_id"])).all()

    if "linked_document_id" in data:
        if not isinstance(data["linked_document_id"], list):
            data["linked_document_id"] = [data["linked_document_id"]]
        tmp_doc["linked_documents"] = Document.query.filter(Document.id.in_(data["linked_document_id"])).all()

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    tmp_doc["date_insert"] = now
    tmp_doc["date_update"] = now

    user = current_app.get_current_user()
    tmp_doc["user_id"] = user.id
    doc = Document(**tmp_doc)

    try:
        db.session.add(doc)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return make_400(str(e))

    return make_200(data=doc.serialize())


@api_bp.route('/api/<api_version>/documents', methods=['PUT'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_put_documents(api_version):
    data = request.get_json()
    if "data" in data:
        data = data["data"]

    tmp_doc = Document.query.filter(Document.id == data.get('id', None)).first()
    if tmp_doc is None:
        return make_404("Document not found")

    is_another_teacher = forbid_if_another_teacher(current_app, tmp_doc.user_id)
    if is_another_teacher:
        return is_another_teacher

    if "title" in data: tmp_doc.title = data["title"]
    if "subtitle" in data: tmp_doc.subtitle = data["subtitle"]
    if "argument" in data: tmp_doc.argument = data["argument"]
    if "pressmark" in data: tmp_doc.pressmark = data["pressmark"]
    if "creation" in data: tmp_doc.creation = data["creation"]
    if "creation_lab" in data: tmp_doc.creation_lab = data["creation_lab"]
    if "copy_year" in data: tmp_doc.copy_year = data["copy_year"]
    if "copy_cent" in data: tmp_doc.copy_cent = data["copy_cent"]

    if "institution_id" in data:
        tmp_doc.institution = Institution.query.filter(Institution.id == data["institution_id"]).first()

    if "editor_id" in data:
        if not isinstance(data["editor_id"], list):
            data["editor_id"] = [data["editor_id"]]
        tmp_doc.editors = Editor.query.filter(Editor.id.in_(data["editor_id"])).all()

    if "country_id" in data:
        if not isinstance(data["country_id"], list):
            data["country_id"] = [data["country_id"]]
        tmp_doc.countries = Country.query.filter(Country.id.in_(data["country_id"])).all()

    if "district_id" in data:
        if not isinstance(data["district_id"], list):
            data["district_id"] = [data["district_id"]]
        tmp_doc.districts = District.query.filter(District.id.in_(data["district_id"])).all()

    if "acte_type_id" in data:
        if not isinstance(data["acte_type_id"], list):
            data["acte_type_id"] = [data["acte_type_id"]]
        tmp_doc.acte_types = ActeType.query.filter(ActeType.id.in_(data["acte_type_id"])).all()

    if "language_code" in data:
        if not isinstance(data["language_code"], list):
            data["language_code"] = [data["language_code"]]
        tmp_doc.languages = Language.query.filter(Language.code.in_(data["language_code"])).all()

    if "tradition_id" in data:
        if not isinstance(data["tradition_id"], list):
            data["tradition_id"] = [data["tradition_id"]]
        tmp_doc.traditions = Tradition.query.filter(Tradition.id.in_(data["tradition_id"])).all()

    if "linked_document_id" in data:
        if not isinstance(data["linked_document_id"], list):
            data["linked_document_id"] = [data["linked_document_id"]]
        tmp_doc.linked_documents = Document.query.filter(Document.id.in_(data["linked_document_id"])).all()

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tmp_doc.date_update = now

    try:
        doc = Document(**tmp_doc)
        db.session.add(doc)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return make_400(str(e))

    return make_200(data=doc.serialize())


@api_bp.route('/api/<api_version>/documents/<doc_id>', methods=['DELETE'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_delete_documents(api_version, doc_id):
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404("Document not found")

    is_another_teacher = forbid_if_another_teacher(current_app, doc.user_id)
    if is_another_teacher:
        return is_another_teacher

    try:
        db.session.delete(doc)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return make_400("Cannot delete data: %s" % str(e))

    return make_204()


@api_bp.route('/api/<api_version>/documents/<doc_id>/whitelist', methods=['POST'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_change_documents_whitelist(api_version, doc_id):
    """
    {
        "data" : {
            "whitelist_id" : 1
        }
    }
    :param api_version:
    :param doc_id:
    :return:
    """

    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404()

    forbid_to_other_teachers = forbid_if_another_teacher(current_app, doc.user_id)
    if forbid_to_other_teachers:
        return forbid_to_other_teachers

    data = request.get_json()
    data = data.get('data')

    try:
        new_white_list_id = data.get('whitelist_id')
        if new_white_list_id is None or int(new_white_list_id) == -1:
            doc.whitelist_id = None
        else:
            wl = Whitelist.query.filter(Whitelist.id == new_white_list_id).first()
            doc.whitelist = wl
        db.session.commit()
    except Exception as e:
        return make_400(str(e))

    return make_200(data=doc.serialize())


@api_bp.route('/api/<api_version>/documents/<doc_id>/close', methods=['POST'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_change_documents_closing_date(api_version, doc_id):
    """
    {
        "data" : {
            "closing_date" : "15/10/2020"
        }
    }
    # dd/mm/YYYY
    :param api_version:
    :param doc_id:
    :return:
    """

    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404()

    is_another_teacher = forbid_if_another_teacher(current_app, doc.user_id)
    if is_another_teacher:
        return is_another_teacher

    data = request.get_json()
    data = data.get('data')
    try:
        new_closing_date = data.get('closing_date')
        if not new_closing_date or len(new_closing_date) == 0:
            new_closing_date = None
        else:
            new_closing_date = datetime.datetime.strptime(new_closing_date, '%d/%m/%Y')
            new_closing_date = new_closing_date.strftime('%Y-%m-%d %H:%M:%S')

        doc.date_closing = new_closing_date
        db.session.commit()
    except Exception as e:
        return make_400(str(e))

    return make_200(data=doc.serialize())


@api_bp.route('/api/<api_version>/documents/add', methods=['POST'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_add_document(api_version):

    data = request.get_json()
    data = data["data"]

    user = current_app.get_current_user()
    kwargs = {
        "title": data.get('title'),
        "subtitle": data.get('subtitle'),
        "user_id": user.id,
        "is_published": 0,
    }

    new_doc = Document(**kwargs)
    db.session.add(new_doc)
    db.session.commit()
    return make_200(data=new_doc.serialize())


@api_bp.route('/api/<api_version>/documents/<doc_id>/set-manifest', methods=['POST'])
@jwt_required
@forbid_if_nor_teacher_nor_admin
def api_set_document_manifest(api_version, doc_id):
    doc = Document.query.filter(Document.id == doc_id).first()
    if doc is None:
        return make_404()

    is_another_teacher = forbid_if_another_teacher(current_app, doc.user_id)
    if is_another_teacher:
        return is_another_teacher

    data = request.get_json()
    data = data["data"]
    manifest_url = data.get("manifest_url")

    if Image.query.filter(Image.manifest_url == manifest_url).first() or \
            ImageUrl.query.filter(ImageUrl.manifest_url == manifest_url).first():
        return make_409(
            details="This manifest is already used by another document. Please choose another or upload it to another "
                    "URL. "
        )

    # FETCH the manifest
    try:
        op = build_opener()
        manifest = op.open(manifest_url, timeout=20).read()
        manifest = json_loads(manifest)
    except Exception as e:
        return make_400(details="Cannot fetch manifest: %s" % str(e))

    # delete old images
    for old_image in Image.query.filter(Image.doc_id == doc.id).all():
        db.session.delete(old_image)
    for old_image_url in ImageUrl.query.filter(ImageUrl.manifest_url == manifest_url).all():
        db.session.delete(old_image_url)

    # add new images
    for canvas_idx, canvas in enumerate(manifest["sequences"][0]['canvases']):
        for img_idx, img in enumerate(canvas["images"]):
            new_img = Image(manifest_url=manifest_url, canvas_idx=canvas_idx, img_idx=img_idx, doc_id=doc_id)
            new_img_url = ImageUrl(manifest_url=manifest_url, canvas_idx=canvas_idx, img_idx=img_idx,
                                   img_url=img["resource"]["@id"])
            db.session.add(new_img)
            db.session.add(new_img_url)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return make_400(details=str(e))

    return make_200(data=[i.serialize() for i in doc.images])


# IMPORT DOCUMENT VALIDATION STEP ROUTES
from .document_validation import *
