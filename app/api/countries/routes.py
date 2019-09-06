from flask import request, current_app
from sqlalchemy.orm.exc import NoResultFound

from app import db, auth
from app.api.routes import api_bp, json_loads
from app.models import Country
from app.utils import forbid_if_nor_teacher_nor_admin, make_404, make_200, make_409


@api_bp.route('/api/<api_version>/countries')
@api_bp.route('/api/<api_version>/countries/<country_id>')
def api_country(api_version, country_id=None):
    if country_id is None:
        countries = Country.query.all()
    else:
        # single
        at = Country.query.filter(Country.id == country_id).first()
        if at is None:
            return make_404("Country {0} not found".format(country_id))
        else:
            countries = [at]
    return make_200([a.serialize() for a in countries])


@api_bp.route('/api/<api_version>/countries', methods=['DELETE'])
@api_bp.route('/api/<api_version>/countries/<country_id>', methods=['DELETE'])
@auth.login_required
def api_delete_country(api_version, country_id=None):
    access_is_forbidden = forbid_if_nor_teacher_nor_admin(current_app)
    if access_is_forbidden:
        return access_is_forbidden

    if country_id is None:
        countries = Country.query.all()
    else:
        countries = Country.query.filter(Country.id == country_id).all()

    for a in countries:
        db.session.delete(a)

    try:
        db.session.commit()
        return make_200([])
    except Exception as e:
        db.session.rollback()
        print(str(e))
        return make_409(str(e))


@api_bp.route('/api/<api_version>/countries', methods=['PUT'])
@auth.login_required
def api_put_country(api_version):
    access_is_forbidden = forbid_if_nor_teacher_nor_admin(current_app)
    if access_is_forbidden:
        return access_is_forbidden

    try:
        data = request.get_json()

        if "data" in data:
            data = data["data"]

            try:
                modifed_data = []
                for country in data:
                    a = Country.query.filter(Country.id == country["id"]).one()
                    a.label = country.get("label")
                    a.ref = country.get("ref")

                    db.session.add(a)
                    modifed_data.append(a)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return make_409(str(e))

            data = []
            for a in modifed_data:
                r = api_country(api_version=api_version, country_id=a.id)
                data.append(json_loads(r.data)["data"])

            return make_200(data)
        else:
            return make_409("no data")
    except NoResultFound:
        return make_404("Country not found")


@api_bp.route('/api/<api_version>/countries', methods=['POST'])
@auth.login_required
def api_post_country(api_version):
    access_is_forbidden = forbid_if_nor_teacher_nor_admin(current_app)
    if access_is_forbidden:
        return access_is_forbidden

    data = request.get_json()

    if "data" in data:
        data = data["data"]

        created_data = []
        try:
            for country in data:
                a = Country(**country)
                db.session.add(a)
                created_data.append(a)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return make_409(str(e))

        data = []
        for a in created_data:
            r = api_country(api_version=api_version, country_id=a.id)
            data.append(json_loads(r.data)["data"])

        return make_200(data)
    else:
        return make_409("no data")
