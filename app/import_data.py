import csv
import glob
import datetime as dt
import os
import re
import ssl
import urllib

from app.models import Donation, Recipient, DonationType, Donor, DonorAlias, DonorType
from app import db, cache

URL = "https://search.electoralcommission.org.uk/api/csv/Donations?start={start}&rows={pageSize}&query=&sort=AcceptedDate&order=desc&et=pp&et=ppm&et=tp&et=perpar&et=rd&date=Received&from=&to=&rptPd=&prePoll=true&postPoll=true&register=gb&register=ni&register=none&donorStatus=individual&donorStatus=tradeunion&donorStatus=company&donorStatus=unincorporatedassociation&donorStatus=publicfund&donorStatus=other&donorStatus=registeredpoliticalparty&donorStatus=friendlysociety&donorStatus=trust&donorStatus=limitedliabilitypartnership&donorStatus=impermissibledonor&donorStatus=na&donorStatus=unidentifiabledonor&donorStatus=buildingsociety&isIrishSourceYes=true&isIrishSourceNo=true&includeOutsideSection75=true"

# Ignore SSL certificate errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def download_raw_data():
    print("Retrieving data from", URL)
    filename = "raw_data_" + str(dt.date.today()) + ".csv"
    urllib.request.urlretrieve(URL, filename)
    print("Saved", filename)
    return filename


# Check last download
raw_data_file = glob.glob("raw_data_*.csv")
try:
    raw_data_file = raw_data_file[0]
except:
    raw_data_file = ""
    print("No previous raw data detected; downloading fresh copy.")
    raw_data_file = download_raw_data()

# Check if a fresh download is desired
last_download = re.findall(r"\d{4}\-\d{2}\-\d{2}", raw_data_file)
last_download = last_download[0]
last_download = dt.datetime(
    int(last_download[0:4]), int(last_download[5:7]), int(last_download[8:10])
)
last_download_pretty = last_download.strftime("%d %B %Y")
print(
    "Data from the Electoral Commission last downloaded on ",
    last_download_pretty,
    ". Would you like to download a fresh copy?",
    sep="",
)
while True:
    download_choice = input("(Y)es/(N)o:")
    if download_choice == "y" or download_choice == "Y":
        os.remove(raw_data_file)
        print("Removed previous data file (", raw_data_file, ")", sep="")
        download_raw_data()
        break
    elif download_choice == "n" or download_choice == "N":
        print("Using existing data file:", raw_data_file)
        break
    else:
        print("Please select (Y)es or (N)o.")
        continue


def remove_line_breaks(row):
    """Removes lines that contain line breaks within cells"""
    for field in row:
        if row[field].strip() != "TRUE" and row[field].strip() != "FALSE":
            # If the field doesn't contain "TRUE" or "FALSE", remove any line breaks
            row[field] = row[field].replace("\n", " ").replace("\r", "")
    return row


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

for donation_type in DONATION_TYPES:
    query = db.select(DonationType).filter_by(name=donation_type)
    if not db.session.execute(query).scalars().first():
        db.session.add(DonationType(name=donation_type))

for donor_type in DONOR_TYPES:
    query = db.select(DonorType).filter_by(name=donor_type)
    if not db.session.execute(query).scalars().first():
        db.session.add(DonorType(name=donor_type))

with open(raw_data_file, newline="") as infile:
    reader = csv.DictReader(infile)
    for record in reader:
        if not relevancy_check(record):
            continue
        # Recipient
        if re.search(r"De-registered", record["RegulatedEntityName"]):
            deregistered = record["RegulatedEntityName"].split()[-1]
            deregistered = dt.datetime.strptime(deregistered, "%d/%m/%y]")
            recipient_name = re.split(r"( \[)", record["RegulatedEntityName"])
            recipient_name = recipient_name[0]
        else:
            recipient_name = record["RegulatedEntityName"]
            deregistered = None

        query = db.select(Recipient).filter_by(name=recipient_name)
        if not db.session.execute(query).scalars().first():
            print(f"New Recipient: {recipient_name}")
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
            print(f"New donor: {donor}")
            donor_list = [donor]
            new_alias = DonorAlias(name=donor_name)
            new_alias.donors.append(donor)
            db.session.add(new_alias)

        db.session.commit()

        # Donation
        ec_ref = record["\ufeffECRef"]
        date = record["ReceivedDate"] or record["AcceptedDate"]
        date = dt.datetime.strptime(date, "%d/%m/%Y")

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
            print(f"{new_donation} added")
            db.session.add(new_donation)

    db.session.commit()

cache.clear()
