from app import create_app

app = create_app()
app.app_context().push()

from datetime import date, datetime
from flask import current_app
import csv
import re
from rq import get_current_job
import ssl
import sys
import urllib

from app import db, cache
from app.models import (
    Donation,
    Recipient,
    DonationType,
    Donor,
    DonorAlias,
    DonorType,
    Task,
)


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


def _set_task_progress(progress):
    job = get_current_job()
    if job:
        job.meta["progress"] = progress
        job.save_meta()
        task = db.session.scalars(db.select(Task).filter_by(id=job.get_id())).first()
        # TODO: build notification
        if progress >= 100 and task.complete == False:
            task.complete = True
        db.session.commit()

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

def import_record(record):
    if not relevancy_check(record):
        return
    record = remove_line_breaks(record)

    # Recipient
    if re.search(r"De-registered", record["RegulatedEntityName"]):
        deregistered = record["RegulatedEntityName"].split()[-1]
        deregistered = datetime.strptime(deregistered, "%d/%m/%y]")
        recipient_name = re.split(r"( \[)", record["RegulatedEntityName"])[
            0
        ]
    else:
        recipient_name = record["RegulatedEntityName"]
        deregistered = None

    query = db.select(Recipient).filter_by(name=recipient_name)
    if not db.session.execute(query).scalars().first():
        recipient = Recipient(
            name=recipient_name, deregistered=deregistered
        )
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
        donor = (
            db.session.execute(query).scalars().first()
        )  # pragma: no cover
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



def download_raw_data():  # pragma: no cover
    # Ignore SSL certificate errors
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    print("Contacting server...")
    filename = "raw_data_" + str(date.today()) + ".csv"
    urllib.request.urlretrieve(URL, filename)
    # A fudge. Calling 2 methods from routes, one after another, was bad because it
    # would require the route to know when download_raw_data was finished. Putting both
    # download_raw_data and db_import in tasks was bad because there was no way to set a
    # combined progress. Instead, we make 1 task and make up a rough progress
    # percentage.
    return filename

def db_import():
    try:
        if current_app.config["TESTING"]:
            downloaded_data = current_app.config["RAW_DATA_LOCATION"] + "raw_data_2023-01-01.csv"
        else:
            _set_task_progress(0)
            downloaded_data = download_raw_data()
            _set_task_progress(5)
        for donation_type in DONATION_TYPES:
            query = db.select(DonationType).filter_by(name=donation_type)
            if not db.session.execute(query).scalars().first():  # pragma: no cover
                db.session.add(DonationType(name=donation_type))
        for donor_type in DONOR_TYPES:  # pragma: no cover
            query = db.select(DonorType).filter_by(name=donor_type)
            if not db.session.execute(query).scalars().first():  # pragma: no cover
                db.session.add(DonorType(name=donor_type))

        with open(downloaded_data, newline="") as infile:
            reader = csv.DictReader(infile)
            total_records = 0
            for record in reader:
                total_records += 1

        with open(downloaded_data, newline="") as infile:
            reader = csv.DictReader(infile)
            for index, record in enumerate(reader):
                import_record(record)
                # Fake percentage function
                if current_app.config["TESTING"]:
                    db.session.commit()
                else:
                    _set_task_progress(round(((index / total_records * 95)) + 5, 2))
                    # Session commit will be handled by _set_task_progress
        cache.clear()
    except:
        app.logger.error("Unhandled exception", exc_info=sys.exc_info())
    finally:
        if not current_app.config["TESTING"]:
            _set_task_progress(100)
