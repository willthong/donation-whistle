# Donation Whistle

A Python application to retrieve, clean and visualise data from the UK Electoral
Commission's [register of donations to political
parties](https://search.electoralcommission.org.uk). The application will pull an
up-to-date donation dataset from the Electoral Commission website, place the data into a
SQLite database and clean it. It aims to fix the biggest problems with the way the
Electoral Commission makes this important public data available: that it does not
consolidate aliases, and that it double-reports donations. Then, it will allow a user to
re-export to CSV, visualise and publicly publish the data.

## Installation / Usage

For your convenience, Donation Whistle is packaged as a Docker image. You can run it as
follows:

1. Clone this repository to your local machine
2. Navigate to the new donation-whistle directory
3. Run `docker-compose up -d`; Donation Whistle will by default run on `localhost:80`
4. Go to the homepage (by default <http://localhost:5000/index>) and create the default
   admin account by going to *Login* on the top bar
5. Log in with the username `admin` and the default password `changethispassword`
6. Perform an initial download of the Electoral Commission's data by choosing *Data
   import* on the top bar; refresh the homepage to see the newly-imported records
5. (Optionally) import an alias file, like the example
   `donation_whistle_alias_export_2023-11-22.json` provided in this repository, by going
   to *Aliases* then *Import/export aliases*

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
* [X] Data import UI (including async import and live progress)
* [X] Alias import/export
* [X] Add reported name to donor detail table
* [X] Write tests
* [X] Dockerized
* [ ] Write and link to a blog post to explain why this project exists
* [ ] Election view for the 12 months leading up to an election

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
