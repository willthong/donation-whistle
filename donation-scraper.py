import urllib.request, urllib.parse, urllib.error
import json
import ssl
from datetime import datetime
from datetime import date
import glob
import re
import os

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


# Check last download
raw_data_file = glob.glob("raw_data_*.csv")
if raw_data_file == []:
    print("No previous raw data detected; downloading fresh copy.")
    download_raw_data()
else:
    # Check if a fresh download is desired
    last_download = re.findall(r"\d{4}\-\d{2}\-\d{2}", raw_data_file[0])
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
            os.remove(raw_data_file[0])
            print("Removed previous data file (", raw_data_file[0], ")", sep="")
            download_raw_data()
            break
        elif download_choice == "n" or download_choice == "N":
            print("Using existing data file.")
            break
        else:
            print("Please select (Y)es or (N)o.")
            continue

#   try:
#       js = json.loads(data)
#   except:
#       js = None

#   if not js or "status" not in js or js["status"] != "OK":
#       print("==== Failure To Retrieve ====")
#       print(data)
#       continue

#   print(json.dumps(js, indent=4))

#   lat = js["results"][0]["geometry"]["location"]["lat"]
#   lng = js["results"][0]["geometry"]["location"]["lng"]
#   print("lat", lat, "lng", lng)
#   location = js["results"][0]["formatted_address"]
#   print(location)
#   try:
#       country_code = js["results"][0]["address_components"][4]["short_name"]
#   except:
#       country_code = "No country code"
#   print("Country code:", country_code)
