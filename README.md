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

* Docker
* Web frontend to explore data?

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
* [ ] Simple import UI
* [ ] Data export as CSV
* [ ] Data import UI (including async import and progress bar)
* [ ] Alias import/export
* [ ] Election view for the 12 months leading up to an election
* [ ] Write and link to a blog post to explain why this project exists

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
