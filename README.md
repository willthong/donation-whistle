# Donation Scraper

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
python3 donation_scraper.py

```

## Roadmap

* [x] Download raw data and save as CSV
* [x] Fix line break errors
* [ ] Import raw data into SQLite database using SQLAlchemy, with 'sane defaults'
  (exclude double-reported gifts)
* [ ] Define aliases
* [ ] User accounts
* [ ] Allow exploration of data (tabular), including with 'sane default' filters
  (central party only; group aliases, including trade unions; exclude public funds)
* [ ] Allow exploration of data (graphical)

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)
