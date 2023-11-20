import datetime as dt
import dateutil.relativedelta as relativedelta
import json
import os
import rq
import sys
import unittest

# Move up a directory to import app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.append(parent_dir)

from config import Config
from flask import current_app
from flask_login import current_user

from app import create_app, db
from app.models import (
    User,
    Donation,
    DonorAlias,
    Donor,
    DonorType,
    DonationType,
    Recipient,
    Task,
)
from app.models import load_user

from app.db_import import tasks as db_import
from app.api import routes as api
from app.main import routes as main


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

    def test_login(self):
        response = self.client.post(
            "/login",
            follow_redirects=True,
            data={"username": "barry", "password": "foobar"},
        )
        assert (
            '="alert alert-info" role="alert">Invalid username or password</div>'
            in response.text
        )
        response = self.client.post(
            "/login",
            follow_redirects=True,
            data={"username": "bob", "password": "not_foobar"},
        )
        assert (
            '="alert alert-info" role="alert">Invalid username or password</div>'
            in response.text
        )
        self.login()
        response = self.client.get("/login", follow_redirects=False)
        assert response.location == "/index"

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
        response = self.client.post("/users/delete/1", follow_redirects=True)
        assert '-info" role="alert">You are the last admin, so you can' in response.text
        response = self.client.post(
            "/register",
            data={
                "username": "admin2",
                "email": "bobthesecond@mailinator.com",
                "is_admin": True,
                "password": "adminpassword",
                "repeat_password": "adminpassword",
            },
            follow_redirects=True,
        )
        response = self.client.get("/users/delete/1", follow_redirects=True)
        assert "This will log you out, as this user is you." in response.text
        admin2 = db.session.execute(
            db.select(User).where(User.username == "admin2")
        ).all()
        response = self.client.post("/users/delete/2", follow_redirects=True)
        admin2 = db.session.execute(
            db.select(User).where(User.username == "admin2")
        ).all()
        assert admin2 == []
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
        assert response.request.path == "/users"
        self.logout()
        response = self.client.post(
            "/login",
            data={"username": "alice", "password": "spamandeggs"},
            follow_redirects=True,
            # Not an admin
        )
        assert response.status_code == 200
        assert '<a class="nav-link" href="/logout">Log out</a>' in response.text
        response = self.client.get("/register", follow_redirects=True)
        assert '-info" role="alert">Only admins can create new users' in response.text
        response = self.client.get("/users", follow_redirects=True)
        assert '-info" role="alert">Only admins can access the user' in response.text
        response = self.client.get("/users/delete/1", follow_redirects=True)
        assert '-info" role="alert">Only admins can delete' in response.text

    def test_check_last_admin(self):
        with self.client:
            self.login()
            assert current_user.check_last_admin()

    def test_create_default_admin(self):
        db.session.delete(
            db.session.scalars(db.select(User).where(User.username == "bob")).one()
        )
        db.session.commit()
        response = self.client.get("/login", follow_redirects=True)
        assert 'alert alert-info" role="alert">Default admin user reg' in response.text

    def test_jobs(self):
        with self.client:
            self.login()
            assert current_user.get_task_in_progress() == None
            assert current_user.launch_task().user == current_user
            # Can't test _set_task_progress because "calling get_current_job() outside of the
            # context of a job function will return None.
            # https://python-rq.org/docs/jobs/#accessing-the-current-job-from-within-the-job-function
            assert current_user.get_tasks_in_progress()[0].user == current_user
            assert current_user.get_task_in_progress().user == current_user
            assert isinstance(
                db.session.scalars(db.select(Task)).first().get_rq_job(), rq.job.Job
            )
            assert db.session.scalars(db.select(Task)).first().get_progress() == 100

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
        response = self.client.get("/db_import/dl_and_import")
        assert "01 January 2023" in response.text

    def db_import(self):
        self.login()
        db_import.db_import()

    def test_db_import(self):
        self.db_import()
        assert db.session.query(DonationType).filter_by(name="Cash").first() is not None
        assert (
            db.session.query(DonorType).filter_by(name="Individual").first() is not None
        )
        dereg_query = db.session.query(Recipient).filter_by(name="All For Unity")
        dereg_query = dereg_query.first().deregistered
        assert dereg_query == dt.date(2022, 5, 6)
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
        db_import.add_missing_entries(DonorType)

    def test_select_type_list(self):
        assert db_import.select_type_list(DonationType) == db_import.DONATION_TYPES
        assert db_import.select_type_list(DonorType) == db_import.DONOR_TYPES
        assert db_import.select_type_list("foobar") is None

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
            "date": dt.date(2019, 12, 1),
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
        assert "<h2>Unite the Union</h2>" in response.text

        response = self.client.post(
            '/alias/new?selected_donors=["11","4","14"]',
            follow_redirects=True,
            data={
                "alias_name": "Unite the Union",
                "note": "Did you hear that? They've shut down the main reactor.",
            },
        )
        assert (
            """<a href="/alias/16">Unite the Union</a>,
          which refers to:</li>"""
            in response.text
        )
        response = self.client.get("/alias/16")
        assert "Did you hear that? They&#39;ve shut down the main" in response.text

        response = self.client.post(
            '/alias/new?selected_donors=["3","5"]',
            follow_redirects=True,
            data={"alias_name": "Unite the Union"},
        )
        assert 'info" role="alert">That alias name is already taken.' in response.text

        # Add alias (TODO when built; you'd just take 14 from above and put it here)
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
            data={"alias_name": "Unite the Union"},
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
            db.session.scalars(db.select(DonorAlias).filter_by(id=31)).first().name
            == "Unite the Union"
        )

        request = self.client.get("/alias/import")
        assert (
            '<form action="" method="POST" enctype="multipart/form-data">'
            in request.text
        )
        assert "downloading them as a JSON file or upload" in request.text

    def test_index_filters(self):
        self.db_import()
        response = self.client.post(
            "/index",
            data={
                "recipient_labour_party": "y",
                "recipient_conservative_and_unionist_party": "y",
                "recipient_liberal_democrats": "y",
                "recipient_scottish_national_party_snp": "y",
                "recipient_green_party": "n",
                "recipient_reform_uk": "y",
                "recipient_other": "y",
                "donor_type_individual": "n",
                "donor_type_company": "y",
                "donor_type_trade_union": "y",
                "donor_type_unincorporated_association": "y",
                "donor_type_other": "n",
                "donor_type_limited_liability_partnership": "y",
                "donor_type_trust": "y",
                "donor_type_friendly_society": "n",
                "donation_type_cash": "y",
                "donation_type_non_cash": "y",
                "donation_type_visit": "n",
                "donation_type_other": "y",
                "is_legacy_true": "y",
                "is_legacy_false": "n",
                "date_gt": "2005-03-02",
                "date_lt": "2020-01-01",
            },
            follow_redirects=True,
        )
        assert (
            "/api/data?filter=recipient_labour_party&filter=recipient_conservative_and_unionist_party&filter=recipient_liberal_democrats&filter=recipient_scottish_national_party_snp&filter=recipient_reform_uk&filter=recipient_other&filter=donor_type_company&filter=donor_type_trade_union&filter=donor_type_unincorporated_association&filter=donor_type_limited_liability_partnership&filter=donor_type_trust&filter=donation_type_cash&filter=donation_type_non_cash&filter=donation_type_other&filter=is_legacy_true&filter=date_gt_2005-03-02&filter=date_lt_2020-01-01"
            in response.text
        )

        query = db.select(Donation)
        query = main.apply_date_filters(
            query, ["date_gt_2019-11-28", "date_lt_2021-04-17"]
        )
        assert len(db.session.scalars(query).all()) == 11

        query = (
            db.session.query(
                DonorAlias.name,
                Donor.donor_type_id,
                db.func.sum(Donation.value).label("donations"),
            )
            .join(Donor.donor_alias)
            .join(Donation)
            .join(DonationType)
            .group_by(DonorAlias.name)
            .order_by(db.desc("donations"))
        )

        donor_type, relevant_types = main.assign_colours_to_donor_types(query, 1)
        assert donor_type == [
            "slateblue",
            "indigo",
            "black",
            "indigo",
            "slateblue",
            "slateblue",
            "indigo",
            "indigo",
            "slateblue",
            "slateblue",
            "indigo",
            "indigo",
            "hotpink",
            "hotpink",
            "hotpink",
        ]
        assert relevant_types == {
            "Company": "slateblue",
            "Individual": "indigo",
            "Other": "black",
            "Trade Union": "hotpink",
        }

    def test_recipient_page(self):
        self.db_import()
        response = self.client.get("/recipient/1", follow_redirects=True)
        assert (
            '"marker":{"color":["slateblue","slateblue","slateblue","indigo","slateblue","slateblue"]},"showlegend":false,"x":["Simon J Collins & Associates Limited","Redsky Wholesalers Ltd","M & M Supplies (UK) PLC","Hugh Sloane","KGL (Estates) Ltd","Thompson Crosby & Co Ltd"],"y":[50000.0,13333.4,12498.0,10705.0,10000.0,8332.0],"type":"bar"}'
            in response.text
        )

    def test_assign_colours_to_parties(self):
        assert (
            main.assign_colours_to_parties("Conservative and Unionist Party")
            == "rgb(0, 135, 220)"
        )
        assert main.assign_colours_to_parties("Not a Party") == "black"

    def test_donor_page(self):
        self.db_import()
        response = self.client.get("/donor/1", follow_redirects=True)
        assert "<h1>Donor detail: KGL (Estates) Ltd" in response.text

    def test_donors_page(self):
        self.db_import()
        response = self.client.get("/donors", follow_redirects=True)
        assert "<h1>All donors<br>" in response.text
        assert (
            '"indigo","indigo","slateblue","slateblue","indigo","indigo","slateblue","slateblue","indigo","indigo","hotpink","hotpink","hotpink"]},"showlegend":false,"x":["Simon J Collins & Associates Limited","Mr Geoff Roper","Miss Moira'
            in response.text
        )
        assert (
            'Union","Unite"],"y":[50000.0,25000.0,14928.53,13333.4,12498.0,10705.0,10000.0,10000.0,8332.0,8196.0,6895.0,6825.0,2500.0,1565.0],"type":"bar"},{"line":{"color":"rgba(0,0,0,0.0)"},"marker":{"color":"slateblue","size":80},"name":"Company","x":[null],"y":[null],"type":"scatter"},{"line":{"color":"rgba(0,0,0,0.0)"},"marker":{"color":"indigo","size":80},"name":"Individual","x":[null],"y":[null],"type":"scatter"},{"line":{"color":"rgba(0,0,0,0.0)"},"marker":{"color":"hotpink","size":80}'
            in response.text
        )

    def test_update_party_sums(self):
        self.db_import()
        parties = {}
        start_date = (
            db.session.query(db.func.min(Donation.date)).first()[0].replace(day=1)
        )
        end_date = db.session.query(db.func.max(Donation.date)).first()[0]
        date_series = []
        while start_date < end_date:
            date_series.append(start_date)
            start_date += relativedelta.relativedelta(months=1)

        for key in main.MAIN_PARTIES:
            parties[key] = [0 for i in range(0, len(date_series))]
        party_stats_query = (
            db.session.query(
                Recipient.name,
                db.func.strftime("%Y-%m", Donation.date).label("month"),
                db.func.sum(Donation.value),
                Recipient.id,
            )
            .join(Recipient)
            .join(Donor)
            .join(DonationType)
            # .where(db.not_(db.or_(*donation_type_filter_statements)))
            # .where(db.not_(db.or_(*donor_type_filter_statements)))
            .group_by("month", Recipient.name)
            .all()
        )

        for record in party_stats_query:
            date = dt.datetime.strptime(record[1], "%Y-%m").date()
            index = date_series.index(date)
            parties = main.update_party_sums(
                parties, index, record[0], round(record[2], 2)
            )
        assert parties == {
            "Conservative and Unionist Party": [
                50000.0,
                54868.4,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                18617.96,
            ],
            "Labour Party": [
                1565.0,
                9325.0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ],
            "Liberal Democrats": [
                25000.0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ],
            "Reform UK": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "All other parties": [
                0,
                30019.53,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                10000.0,
                0,
                0,
            ],
        }

        response = self.client.get("/recipients", follow_redirects=True)
        assert (
            '{"data":[{"customdata":["Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party","Conservative Party"],"histfunc":"sum","hovertemplate":"'
            in response.text
        )
        assert (
            'marker":{"color":"rgb(0, 135, 220)"},"name":"Conservative Party","x":["2019-11-01","2019-12-01","2020-01-01","2020-02-01","2020-03-01","2020-04-01","2020-05-01","2020-06-01","2020-07-01","2020-08-01","2020-09-01","2020-10-01","2020-11-01","2020-12'
            in response.text
        )

    def test_notifications(self):
        with self.client:
            self.login()
            response = self.client.get("/notifications")
            assert response.text == "null\n"
            current_user.add_notification(
                "task_progress", {"task_id": 12345, "progress": 42}
            )
            response = self.client.get("/notifications")
            assert (
                '{"data":{"progress":42,"task_id":12345},"name":"task_progress","timestamp":'
                in response.text
            )
