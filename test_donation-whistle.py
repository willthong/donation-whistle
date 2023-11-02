import os
# In-memory database - has to go before calling current_app in order to form part of the
# global scope, otherwise it'll be overwritten
os.environ["DATABASE_URL"] = "sqlite://"

import unittest

from flask import current_app
from app import create_app, db


class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.appctx = self.app.app_context()
        self.appctx.push()
        db.create_all()
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

