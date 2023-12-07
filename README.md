# Donation Whistle

A Python application to retrieve, clean and visualise data from the UK Electoral
Commission's [register of donations to political
parties](https://search.electoralcommission.org.uk). The application will pull an
up-to-date donation dataset from the Electoral Commission website, place the data into a
SQLite database and clean it. It aims to fix the biggest problems with the way the
Electoral Commission makes this important public data available: that it does not
consolidate aliases, and that it double-reports donations. Then, it will allow a user to
re-export to CSV, visualise and publicly publish the data.

Read more about Donation Whistle at [my blog](willthong.com/donation-whistle.html).
There is also a video tour which you can watch below.

[![Donation Whistle Video Tour](https://img.youtube.com/vi/ucK58NF6xSs/maxresdefault.jpg)](https://youtu.be/ucK58NF6xSs)

## Installation

For your convenience, Donation Whistle is packaged as a Docker image.

`docker-compose.yaml` is a testing configuration which will set up Donation Whistle on
your local machine; you can run it with `docker-compose up -d`. Donation Whistle should
then be accessible via `localhost:80`.

Alternatively, to deploy on a production server, use `docker-compose.staging.yaml`. It
uses [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) to set up a container and
generate a reverse proxy so that the appropriate host address you control (eg
`donationwhistle.willthong.com`) can redirect to the application running on the Docker
container on your server. You will need to set up DNS so that the address points to your
server (see eg
[here](https://www.namecheap.com/support/knowledgebase/article.aspx/319/2237/how-can-i-set-up-an-a-address-record-for-my-domain/)
for how to do so if Namecheap is your hosting providor). Then follow these steps to get
the container working:

1. Download `docker-compose.prod.yaml` to your server
2. Edit the LETSENCRYPT_HOST and VIRTUAL_HOST variables so they both match your host
   address (the web address you expect your Donation Whistle instance to be accessed
   through, eg `donationwhistle.willthong.com`)
3. Create a file called `.env.prod.proxy-companion` in the samme directory as
   `docker-compose.prod.yaml`; it should contain these lines:

```
DEFAULT_EMAIL=[your email address]
NGINX_PROXY_CONTAINER=nginx-proxy
```

4. From the directory containing `docker-compose.prod.yaml`, run `docker-compose -f
   docker-compose.prod.yaml up -d`; Donation Whistle should then be accessible via your
   host address

## Getting started

Whether you're running a testing or production server, follow these steps to get
started:

1. Visit your host address
2. Click 'Login'
3. Log in with the username `admin` and the default password `changethispassword`
4. Perform an initial download of the Electoral Commission's data by choosing *Data
   import* on the top bar
5. When the import is complete (progress will be shown at the top of the page), refresh
   the homepage to see the newly-imported records
6. (Optional) Import an alias file, like the example
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
