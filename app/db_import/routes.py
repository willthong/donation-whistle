from datetime import date, datetime
import csv
import glob
import re
import ssl
import urllib

from flask import redirect, request, render_template, url_for

from app import app, db, cache
from app.db_import import bp
from app.db_import.forms import DBImport
from app.models import Donation, Recipient, DonationType, Donor, DonorAlias, DonorType


URL = "https://search.electoralcommission.org.uk/api/csv/Donations?start={start}&rows={pageSize}&query=&sort=AcceptedDate&order=desc&et=pp&et=ppm&et=tp&et=perpar&et=rd&date=Received&from=&to=&rptPd=&prePoll=true&postPoll=true&register=gb&register=ni&register=none&donorStatus=individual&donorStatus=tradeunion&donorStatus=company&donorStatus=unincorporatedassociation&donorStatus=publicfund&donorStatus=other&donorStatus=registeredpoliticalparty&donorStatus=friendlysociety&donorStatus=trust&donorStatus=limitedliabilitypartnership&donorStatus=impermissibledonor&donorStatus=na&donorStatus=unidentifiabledonor&donorStatus=buildingsociety&isIrishSourceYes=true&isIrishSourceNo=true&includeOutsideSection75=true"


DONATION_TYPES = [
    "Cash",
    "Non Cash",
    "Visit",
    "Public Funds",
    "Exempt Trust",
    "Permissible Donor Exempt Trust",
    "Impermissible Donor",
    "Unidentified Donor",
]

DONOR_TYPES = [
    "Individual",
    "Company",
    "Registered Political Party",
    "Unincorporated Association",
    "Other",
    "Trade Union",
    "Building Society",
    "Public Fund",
    "Limited Liability Partnership",
    "Trust",
    "Friendly Society",
    "Impermissible Donor",
    "N/A",
    "Unidentifiable Donor",
]

# Ignore SSL certificate errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def download_raw_data():
    filename = "raw_data_" + str(date.today()) + ".csv"
    urllib.request.urlretrieve(URL, filename)
    return filename


def relevancy_check(record):
    """Returns True if a record is relevant, or False if not"""
    if (
        record["AccountingUnitName"] != "Central Party"
        or record["DonorStatus"] in ["Unidentifiable Donor"]
        or record["DonationAction"] in ["Returned", "Forfeited"]
        or re.search(r"(referendum)|(election)|(poll)", record["ReportingPeriodName"])
    ):
        return False
    return True


def remove_line_breaks(row):
    """Removes lines that contain line breaks within cells"""
    for field in row:
        if row[field].strip() != "TRUE" and row[field].strip() != "FALSE":
            # If the field doesn't contain "TRUE" or "FALSE", remove any line breaks
            row[field] = row[field].replace("\n", " ").replace("\r", "")
    return row


@app.route("/db_import/db_import", methods=["GET", "POST"])
def db_import():
    form = DBImport()

    if not form.validate_on_submit():
        # Check last download
        raw_data_file = glob.glob("raw_data_*.csv")
        try:
            last_download = re.findall(r"\d{4}\-\d{2}\-\d{2}", raw_data_file[0])
            last_download = datetime.strptime(last_download[0], "%Y-%m-%d")
            last_download = last_download.strftime("%d %B %Y")
        except:
            last_download = None
        return render_template("db_import.html", form=form, last_download=last_download)

    downloaded_data = download_raw_data()

    for donation_type in DONATION_TYPES:
        query = db.select(DonationType).filter_by(name=donation_type)
        if not db.session.execute(query).scalars().first():
            db.session.add(DonationType(name=donation_type))
    for donor_type in DONOR_TYPES:
        query = db.select(DonorType).filter_by(name=donor_type)
        if not db.session.execute(query).scalars().first():
            db.session.add(DonorType(name=donor_type))

    with open(downloaded_data, newline="") as infile:
        reader = csv.DictReader(infile)
        for record in reader:
            if not relevancy_check(record):
                continue
            remove_line_breaks(record)

            # Recipient
            if re.search(r"De-registered", record["RegulatedEntityName"]):
                deregistered = record["RegulatedEntityName"].split()[-1]
                deregistered = datetime.strptime(deregistered, "%d/%m/%y]")
                recipient_name = re.split(r"( \[)", record["RegulatedEntityName"])[0]
            else:
                recipient_name = record["RegulatedEntityName"]
                deregistered = None

            query = db.select(Recipient).filter_by(name=recipient_name)
            if not db.session.execute(query).scalars().first():
                recipient = Recipient(name=recipient_name, deregistered=deregistered)
                db.session.add(recipient)
            else:
                recipient = db.session.execute(query).scalars().first()

            # Clean up donor name to remove leading/trailing spaces and double spaces
            donor_name = (
                record["DonorName"]
                .strip()
                .replace("  ", " ")
                .replace("( ", "(")
                .replace(" )", ")")
            )

            # Donors and aliases
            query = db.select(Donor).filter_by(name=donor_name)
            if db.session.execute(query).scalars().first():
                donor = db.session.execute(query).scalars().first()
            else:
                donor = Donor(
                    name=donor_name,
                    ec_donor_id=record["DonorId"],
                    postcode=record["Postcode"],
                    company_registration_number=record["CompanyRegistrationNumber"],
                    donor_type_id=record["DonorStatus"],
                )
                new_alias = DonorAlias(name=donor_name)
                new_alias.donors.append(donor)
                db.session.add(new_alias)
            db.session.commit()

            # Donation
            ec_ref = record["\ufeffECRef"]
            date = record["ReceivedDate"] or record["AcceptedDate"]
            date = datetime.strptime(date, "%d/%m/%Y")

            query = db.select(DonationType).filter_by(name=record["DonationType"])
            donation_type_id = db.session.execute(query).scalars().first().id

            query = db.select(DonorType).filter_by(name=record["DonorStatus"])
            donor_type_id = db.session.execute(query).scalars().first().id

            query = db.select(Donation).filter_by(ec_ref=ec_ref)
            if not db.session.execute(query).scalars().first():
                new_donation = Donation(
                    recipient=recipient,
                    donor=donor,
                    donation_type_id=donation_type_id,
                    value=re.sub(r"[£,]", "", record["Value"]),
                    date=date,
                    ec_ref=ec_ref,
                    is_legacy=record["IsBequest"] == "True",
                )
                db.session.add(new_donation)
        db.session.commit()
    cache.clear()
    return redirect(url_for("index"))
