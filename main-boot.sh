#!/bin/bash

poetry run flask db init
poetry run flask db migrate -m "Initial"
poetry run flask db upgrade
poetry run gunicorn -b :5000 -k gevent --access-logfile - --error-logfile - donation-whistle:app
