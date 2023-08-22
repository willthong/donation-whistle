import csv
import glob
from datetime import date, datetime
from datetime import date
import os
import re
import shutil
import ssl
import urllib.request, urllib.parse, urllib.error

url = "https://search.electoralcommission.org.uk/api/csv/Donations?start={start}&rows={pageSize}&query=&sort=AcceptedDate&order=desc&et=pp&et=ppm&et=tp&et=perpar&et=rd&date=Received&from=&to=&rptPd=&prePoll=true&postPoll=true&register=gb&register=ni&register=none&donorStatus=individual&donorStatus=tradeunion&donorStatus=company&donorStatus=unincorporatedassociation&donorStatus=publicfund&donorStatus=other&donorStatus=registeredpoliticalparty&donorStatus=friendlysociety&donorStatus=trust&donorStatus=limitedliabilitypartnership&donorStatus=impermissibledonor&donorStatus=na&donorStatus=unidentifiabledonor&donorStatus=buildingsociety&isIrishSourceYes=true&isIrishSourceNo=true&includeOutsideSection75=true"

# Ignore SSL certificate errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def download_raw_data():
    print("Retrieving data from", url)
    filename = "raw_data_" + str(date.today()) + ".csv"
    # uh = urllib.request.urlopen(url, context=ctx)
    urllib.request.urlretrieve(url, filename)
    # data = uh.read().decode()
    # print("Retrieved", len(data), "characters")
    print("Saved", filename)
    raw_data_file = filename


# Check last download
raw_data_file = glob.glob("raw_data_*.csv")
try:
    raw_data_file = raw_data_file[0]
except:
    raw_data_file = ""
    print("No previous raw data detected; downloading fresh copy.")
    download_raw_data()

# Check if a fresh download is desired
last_download = re.findall(r"\d{4}\-\d{2}\-\d{2}", raw_data_file)
last_download = last_download[0]
last_download = datetime(
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

# Remove errant line breaks
shutil.copyfile(raw_data_file, "temp.csv")
with open("temp.csv", newline="") as infile:
    reader = csv.reader(infile)
    with open(raw_data_file, "w", newline="") as outfile:
        writer = csv.writer(outfile)
        for row in reader:
            new_row = []
            for field in row:
                if field.strip() == "TRUE" or field.strip() == "FALSE":
                    # If the field contains "TRUE" or "FALSE", don't remove line breaks
                    new_row.append(field)
                else:
                    # Otherwise, remove any line breaks
                    new_row.append(field.replace("\n", " ").replace("\r", ""))
            # Write the updated row to the output file
            writer.writerow(new_row)
    os.remove("temp.csv")

# Put the data into a SQLite database
with open(raw_data_file, newline="") as infile:
    reader = csv.reader(infile)
    for row in reader:
        print(row)
