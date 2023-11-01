# Donation Whistle

A Python application to retrieve, clean and visualise data from the UK Electoral
Commission's [register of donations to political
parties](https://search.electoralcommission.org.uk). The application will pull an
up-to-date donation dataset from the Electoral Commission website, place the data into a
SQLite database and clean it. It aims to fix the biggest problems with the way the
Electoral Commission makes this important public data available: that it does not
consolidate aliases, and that it double-reports donations. Then, it will allow a user to
re-export to CSV, visualise and publicly publish the data.

## Installation

This repository includes a working copy of the database. If anybody wants to try
self-hosting Donation Whistle, this helps them hit the ground running. However, if you
prefer to start from scratch:

1. Delete `donation-whistle.db`
2. Run `poetry shell` to make sure you're in the `poetry` virtual environment
3. Run `flask db init` and `flask db migrate -m "Initial"` to create a new
   `donation-whistle.db` file
4. Perform an initial download of the Electoral Commission's data by going to the
   homepage (by default <http://localhost:5000/index>) and choosing *Data import* on the
   top bar
5. (Optionally) import an alias file, like the example provided in this repository, by
   logging in and going to *Aliases* then *Import/export aliases*

# TODO: create default admin account

* Docker

## Usage

```
poetry update
poetry shell
flask run donation_scraper.py

```

## Roadmap

* [x] Download raw data and save as CSV
* [x] Fix line break errors
* [X] Import raw data into SQLite database using SQLAlchemy, with 'sane defaults'
  (exclude double-reported gifts)
* [X] User accounts
* [X] Define aliases UI
* [X] Allow exploration of data (tabular), including with 'sane default' filters
  (group aliases, including trade unions; exclude public funds)
* [X] Allow exploration of data (graphical)
* [X] Simple import UI
* [X] Data export as CSV
* [ ] Data import UI (including async import and progress bar)
* [X] Alias import/export
* [ ] Election view for the 12 months leading up to an election
* [X] Add reported name to donor detail table
* { } Write tests
* [ ] Write and link to a blog post to explain why this project exists

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
