import os
import sys

# Move up a directory to import app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.append(parent_dir)

from datetime import date
import unittest

from config import Config
from flask import current_app

from app import create_app, db
from app.models import (
    User, 
    Donation, 
    DonorAlias, 
    Donor, 
    DonorType, 
    DonationType, 
    Recipient, 
    load_user
)

from app.db_import import routes as db_import


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
        html = response.get_data(as_text=True)
        assert "<h1>All donations</h1>" in html
        assert 'form action="/"' in html
        assert 'input id="donor_type_individual"' in html
        assert 'div id="table"' in html
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
        html = response.get_data(as_text=True)
        assert "Field must be equal to password." in html

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
        html = response.get_data(as_text=True)
        assert "That username is taken. Please use a different one." in html
        assert "That email is taken. Please use a different one." in html


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
        html = response.get_data(as_text=True)
        assert '<a class="nav-link" href="/logout">Log out</a>' in html

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
        html = response.get_data(as_text=True)
        assert "01 January 2023" in html

    def db_import(self):
        self.login()
        self.client.post("/db_import/db_import")

    def test_db_import(self):
        self.db_import()
        assert db.session.query(DonationType).filter_by(name="Cash").first() is not None
        assert db.session.query(DonorType).filter_by(name="Individual").first() is not None
        dereg_query = db.session.query(Recipient).filter_by(name="All For Unity")
        dereg_query = dereg_query.first().deregistered 
        assert dereg_query == date(2022,5,6)
        assert db.session.query(Donor).filter_by(name="KGL (Estates) Ltd").first() is not None
        assert db.session.query(DonorAlias).filter_by(name="KGL (Estates) Ltd").first() is not None
        assert db.session.query(DonorAlias).count() == 12
        assert db.session.query(Donation).filter_by(ec_ref="C0476383").first().value == 2500
        # Check for dupe EC ref record in raw_data_file
        assert db.session.query(Donation).filter_by(ec_ref="C0476383").count() == 1

    def test_models(self):
        self.db_import()
        assert repr(db.session.query(DonorAlias).filter_by(name="Unite").first()) == "<Donor Unite>"
        assert repr(db.session.query(Donor).filter_by(name="Unite").first()) == "<Donor (Backend) Unite>"
        assert repr(db.session.query(Recipient).filter_by(name="Labour Party").first()) == "<Recipient Labour Party>"
        assert repr(db.session.query(DonationType).filter_by(name="Cash").first()) == "Cash"
        donation = db.session.query(Donation).filter_by(id=1).first()
        repr_string = "<Donation of £10000.0 from KGL (Estates) Ltd"
        repr_string += " to Conservative and Unionist Party on 2019-12-01>"
        assert repr(donation) == repr_string
        assert donation.to_dict() == {
            'donor': 'KGL (Estates) Ltd', 
            'donor_type': 'Company', 
            'alias_id': 1, 
            'recipient': 'Conservative and Unionist Party', 
            'recipient_id': 1, 
            'date': date(2019, 12, 1), 
            'type': 'Cash', 
            'amount': 10000.0, 
            'legacy': False, 
            'original_donor_name': 'KGL (Estates) Ltd', 
            'electoral_commission_donor_id': 37934, 
            'electoral_commission_donation_id': 'C0479200'
        }
        assert repr(db.session.query(User).filter_by(id=1).first()) == "<User bob>" 

    def test_load_user(self):
        assert repr(load_user(1)) == "<User bob>"

