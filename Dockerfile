FROM python:3.11-slim

RUN useradd donation-whistle
WORKDIR /home/donation-whistle

COPY pyproject.toml poetry.lock config.py donation-whistle.py main-boot.sh ./
COPY app app
COPY static static
RUN mkdir cache && mkdir db

ENV POETRY_VERSION=1.7.1
RUN pip install "poetry==$POETRY_VERSION" \
    && poetry config virtualenvs.create false \
    && poetry install --no-root

ENV FLASK_APP donation-whistle.py

RUN chown -R donation-whistle:donation-whistle ./ \ 
    && chmod +x ./main-boot.sh
USER donation-whistle

EXPOSE 5000

ENTRYPOINT ["./main-boot.sh"]
