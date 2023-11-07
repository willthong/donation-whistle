import os
import sys

# Move up a directory to import app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.append(parent_dir)

from datetime import date
from io import BytesIO
import json
import unittest

from config import Config
from flask import current_app
from werkzeug.datastructures import FileStorage

from app import create_app, db
from app.models import (
    User,
    Donation,
    DonorAlias,
    Donor,
    DonorType,
    DonationType,
    Recipient,
    load_user,
)

from app.db_import import routes as db_import
from app.api import routes as api
from app.alias import forms as alias_forms


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    RAW_DATA_LOCATION = "tests/"


class TestWebApp(unittest.TestCase):
    def populate_db(self):
        user = User(username="bob", email="bob@mailinator.com", is_admin=True)
        user.set_password("foobar")
        db.session.add(user)
        db.session.commit()

    def login(self):
        self.client.post("/login", data={"username": "bob", "password": "foobar"})

    def logout(self):
        self.client.get("/logout")

    def setUp(self):
        self.app = create_app(TestConfig)
        self.appctx = self.app.app_context()
        self.appctx.push()
        db.create_all()
        self.populate_db()
        self.client = self.app.test_client()

    def tearDown(self):
        db.drop_all()
        self.appctx.pop()
        self.app = None
        self.appctx = None
        self.client = None

    def test_app(self):
        assert self.app is not None
        assert current_app == self.app

    def test_home_page_redirect(self):
        response = self.client.get("/alias/create_new", follow_redirects=True)
        assert response.status_code == 200
        assert response.request.path == "/login"

    def test_index(self):
        response = self.client.get("/index")
        assert response.status_code == 200
        assert "<h1>All donations</h1>" in response.text
        assert 'form action="/"' in response.text
        assert 'input id="donor_type_individual"' in response.text
        assert 'div id="table"' in response.text
        # Probably not working because there's no data yet. #TODO: come back to this
        # when it is ready.
        # assert 'class="gridjs gridjs-container"' in html

    def test_register_user_not_logged_in(self):
        response = self.client.post("/register")
        assert response.status_code == 302

    def test_register_user_mismatched_passwords(self):
        self.login()
        response = self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@mailinator.com",
                "password": "spamandeggs",
                "repeat_password": "vegan",
            },
        )
        assert response.status_code == 200
        assert "Field must be equal to password." in response.text

    def test_register_user_validation(self):
        self.login()
        response = self.client.post(
            "/register",
            data={
                "username": "bob",
                "email": "bob@mailinator.com",
                "password": "spamandeggs",
                "repeat_password": "spamandeggs",
            },
        )
        assert "That username is taken. Please use a different one." in response.text
        assert "That email is taken. Please use a different one." in response.text

    def test_register_user(self):
        self.login()
        response = self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@mailinator.com",
                "password": "spamandeggs",
                "repeat_password": "spamandeggs",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert response.request.path == "/index"
        self.logout()
        response = self.client.post(
            "/login",
            data={"username": "alice", "password": "spamandeggs"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert '<a class="nav-link" href="/logout">Log out</a>' in response.text

    def test_relevancy_check(self):
        dummy = {
            "AccountingUnitName": "Central Party",
            "DonorStatus": "Individual",
            "DonationAction": "",
            "ReportingPeriodName": "Q2 2023",
        }
        assert db_import.relevancy_check(dummy)
        dummy["AccountingUnitName"] = "Mordor CLP"
        assert not db_import.relevancy_check(dummy)
        dummy["AccountingUnitName"] = "Central Party"
        dummy["DonorStatus"] = "Unidentifiable Donor"
        assert not db_import.relevancy_check(dummy)
        dummy["DonorStatus"] = "Individual"
        dummy["DonationAction"] = "Forfeited"
        assert not db_import.relevancy_check(dummy)
        dummy["DonationAction"] = ""
        dummy["ReportingPeriodName"] = "Pre-poll 5 - Party (27/04/2015 - 03/05/2015)"
        assert not db_import.relevancy_check(dummy)

    def test_remove_line_breaks(self):
        dummy = {
            "DonorName": """G1 GROUP PLC
VIRGINIA HOUSE
""",
            "IsBequest": """TRUE
            """,
        }
        db_import.remove_line_breaks(dummy)
        assert dummy["DonorName"] == "G1 GROUP PLC VIRGINIA HOUSE "
        assert (
            dummy["IsBequest"]
            == """TRUE
            """
        )

    def test_last_download(self):
        self.login()
        response = self.client.get("/db_import/db_import")
        assert "01 January 2023" in response.text

    def db_import(self):
        self.login()
        self.client.post("/db_import/db_import")

    def test_db_import(self):
        self.db_import()
        assert db.session.query(DonationType).filter_by(name="Cash").first() is not None
        assert (
            db.session.query(DonorType).filter_by(name="Individual").first() is not None
        )
        dereg_query = db.session.query(Recipient).filter_by(name="All For Unity")
        dereg_query = dereg_query.first().deregistered
        assert dereg_query == date(2022, 5, 6)
        assert (
            db.session.query(Donor).filter_by(name="KGL (Estates) Ltd").first()
            is not None
        )
        assert (
            db.session.query(DonorAlias).filter_by(name="KGL (Estates) Ltd").first()
            is not None
        )
        assert db.session.query(DonorAlias).count() == 15
        assert (
            db.session.query(Donation).filter_by(ec_ref="C0476383").first().value
            == 2500
        )
        # Check for dupe EC ref record in raw_data_file
        assert db.session.query(Donation).filter_by(ec_ref="C0476383").count() == 1

    def test_models(self):
        self.db_import()
        assert (
            repr(db.session.query(DonorAlias).filter_by(name="Unite").first())
            == "<Donor Unite>"
        )
        assert (
            repr(db.session.query(Donor).filter_by(name="Unite").first())
            == "<Donor (Backend) Unite>"
        )
        assert (
            repr(db.session.query(Recipient).filter_by(name="Labour Party").first())
            == "<Recipient Labour Party>"
        )
        assert (
            repr(db.session.query(DonationType).filter_by(name="Cash").first())
            == "Cash"
        )
        donation = db.session.query(Donation).filter_by(id=1).first()
        repr_string = "<Donation of £10000.0 from KGL (Estates) Ltd"
        repr_string += " to Conservative and Unionist Party on 2019-12-01>"
        assert repr(donation) == repr_string
        assert donation.to_dict() == {
            "donor": "KGL (Estates) Ltd",
            "donor_type": "Company",
            "alias_id": 1,
            "recipient": "Conservative and Unionist Party",
            "recipient_id": 1,
            "date": date(2019, 12, 1),
            "type": "Cash",
            "amount": 10000.0,
            "legacy": False,
            "original_donor_name": "KGL (Estates) Ltd",
            "electoral_commission_donor_id": 37934,
            "electoral_commission_donation_id": "C0479200",
        }
        assert repr(db.session.query(User).filter_by(id=1).first()) == "<User bob>"

    def test_load_user(self):
        assert repr(load_user(1)) == "<User bob>"

    def test_apply_sort(self):
        self.db_import()
        query = db.select(Donation).join(Donor).join(DonorAlias)
        with self.app.test_request_context(
            "/api/data", method="GET", data={"sort": False}
        ):
            query = db.session.scalars(api.apply_sort(query))
            assert query.first().id == 15
        query = db.select(Donation).join(Donor).join(DonorAlias)
        with self.app.test_request_context(
            "/api/data?sort=donor",
            method="GET",
        ):
            query = db.session.scalars(api.apply_sort(query))
            assert query.first().id == 6
        query = db.select(Donation).join(Donor).join(DonorAlias)
        with self.app.test_request_context(
            "/api/data?sort=-donor",
            method="GET",
        ):
            query = db.session.scalars(api.apply_sort(query))
            assert query.first().id == 4

    def test_filters_search_sort_pagination(self):
        self.db_import()

        response = self.client.get(
            "/api/data?filter=recipient_labour_party&filter=date_gt_2019-12-10"
        )
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "C0476397"

        response = self.client.get(
            "/api/data?filter=recipient_labour_party&filter=recipient_other"
        )
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 6
        assert return_data[0]["electoral_commission_donation_id"] == "C0559402"

        response = self.client.get(
            "/api/data?filter=donor_type_individual&filter=donation_type_non_cash"
        )
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "NC0417015"

        response = self.client.get("/api/data?filter=donation_type_other")
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "ET0551995"

        response = self.client.get("/api/data?filter=is_legacy_true")
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "C0418547"

        response = self.client.get(
            "/api/data?filter=is_legacy_false&filter=date_lt_2019-11-01"
        )
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "C0477621"

        response = self.client.get("/api/data?filter=donor_alias_4")
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "C0476383"

        response = self.client.get("/api/data?search=harvie")
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 1
        assert return_data[0]["electoral_commission_donation_id"] == "C0416845"

        response = self.client.get("/api/data?sort=donor")
        return_data = json.loads(response.text)
        assert return_data["total"] == 15
        assert return_data["data"][0]["recipient_id"] == 5

        response = self.client.get("/api/data?start=3&length=2")
        return_data = json.loads(response.text)["data"]
        assert len(return_data) == 2
        assert return_data[0]["recipient_id"] == 3

    def test_aliases(self):
        self.db_import()

        # Aliases
        response = self.client.get("/alias/aliases")
        assert "<li>M &amp; M Supplies (UK) PLC </li>" in response.text

        # create_new alias
        response = self.client.get("alias/create_new")
        assert "<h1>Create a new alias</h1>" in response.text
        assert (
            '<button type="button" class="btn btn-secondary" id="clearButton">'
            in response.text
        )
        assert "Simon J Collins &amp; Associates Limited" in response.text

        # Out of range alias
        with self.assertRaises(Exception) as ctx:
            response = self.client.get(
                '/alias/new?selected_donors=["10302","4"]',
                follow_redirects=True,
            )

        assert "Alias id 10302 does not refer to an alias." in str(ctx.exception)

        # Create alias
        response = self.client.get(
            '/alias/new?selected_donors=["11","4"]',
            follow_redirects=True,
        )
        assert "<h1>Confirm new alias creation?</h1>" in response.text
        assert "<h2> Unite the Union </h2>" in response.text

        response = self.client.post(
            '/alias/new?selected_donors=["11","4","14"]',
            follow_redirects=True,
            data={"alias_name": "Unite the Union"},
        )
        assert (
            """<a href="/alias/16">Unite the Union</a>,
          which refers to:</li>"""
            in response.text
        )

        response = self.client.post(
            '/alias/new?selected_donors=["3","5"]',
            follow_redirects=True,
            data={"alias_name": "Unite the Union"},
        )
        assert 'info" role="alert">That alias name is already taken.' in response.text

        # Add alias (#TODO when built; you'd just take 14 from above and put it here)
        # response = self.client.post(
        #     '/alias/new?selected_donors=["14","16"]',
        #     follow_redirects=True,
        #     data={"alias_name": "Unite the Union"},
        # )
        #
        # assert (
        #     """<a href="/alias/17">Unite the Union</a>,
        #   which refers to:</li>"""
        #     in response.text
        # )
        # assert "Ooonite" in response.text

        # Update alias
        response = self.client.post(
            "/alias/16",
            follow_redirects=True,
            data={"alias_name": "Delete Me", "alias_note": "Ready for deletion"},
        )
        assert "<h1>Alias detail: Delete Me</h1>" in response.text

        # Delete donor from alias
        response = self.client.get("/alias/delete/16/14")
        assert "Are you sure you want Ooonite to be listed separately?" in response.text
        response = self.client.post("/alias/delete/16/14")
        donors = (
            db.session.scalars(db.select(DonorAlias).filter_by(id=16)).first().donors
        )
        assert [donor.id for donor in donors] == [4, 11]

        response = self.client.get("/alias/delete/16")
        assert "<h1>Confirm delete alias: Delete Me</h1>" in response.text

        # Delete alias altogether
        response = self.client.post("/alias/delete/16")
        assert (
            len(db.session.scalars(db.select(DonorAlias).filter_by(id=16)).all()) == 1
        )

    def test_export_aliases(self):
        self.db_import()
        response = self.client.get("/alias/export")
        assert json.loads(response.text)[5]["donors"] == ["Mr Edward T Baxter"]

    def test_import_aliases(self):
        self.db_import()
        self.client.post(
            '/alias/new?selected_donors=["11","4"]', 
            follow_redirects=True, 
            data={"alias_name": "Unite the Union"}
        )

        with self.assertRaises(Exception) as ctx:
            self.client.post(
                "/alias/import",
                follow_redirects=True, 
                data={"json": open("tests/bad_json.json", "rb")},
            )
        assert "Error decoding JSON:" in str(ctx.exception)

        self.client.post(
            "/alias/import",
            follow_redirects=True, 
            data={"json": open("tests/dummy_alias_export.json", "rb")},
        )
        assert (
            db.session.scalars(db.select(DonorAlias).filter_by(id=31)).first().name == "Unite the Union"
        ) 

        request = self.client.get("/alias/import")
        assert '<form action="" method="POST" enctype="multipart/form-data">' in request.text
        assert "downloading them as a JSON file or upload" in request.text

