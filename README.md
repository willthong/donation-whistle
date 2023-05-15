# Donation Scraper

A Python application to retrieve, clean and visualise data from the UK Electoral
Commission's [register of donations to political
parties](https://search.electoralcommission.org.uk). The application will pull an
up-to-date donation dataset from the Electoral Commission website, place the data into a
SQLite database and clean it. Then, it will allow a user to re-export to CSV and,
eventually, visualise the data.

## Installation

* Docker
* Web frontend to explore data?

## Usage

```
python3 donation_scraper.py

```

## Roadmap

- [x] Download raw data and save as CSV
- [ ] Fix line break errors
- [ ] Import raw data into SQLite database
- [ ] Clean data in SQLite
- [ ] Allow exploration of data (tabular)
- [ ] Allow exploration of data (graphical)

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[GNU GPLv3](https://choosealicense.com/licenses/gpl-3.0/#)
