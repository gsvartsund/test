import csv
import json
import logging
import re
from datetime import datetime

from errors import DataFileError, InvalidOfferError
from models import Offer, TIME_PRESETS

ID_PATTERN = re.compile(r"^(?:OF\d{4}|Offer\d+)$")
DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d")

COLUMNS = [
    "offer_id", "company", "destination", "date", "departure",
    "arrival_date", "arrival", "price", "transfers", "luggage_kg",
    "changeable", "refundable", "seats", "rating"
]


def read_csv_file(path, needed_columns):
    try:
        data_file = open(path, newline="", encoding="utf-8")
    except FileNotFoundError:
        logging.error("File not found: %s", path)
        raise DataFileError("Could not find the file: " + path)

    with data_file:
        reader = csv.DictReader(data_file)
        columns = reader.fieldnames
        rows = list(reader)

    if columns is None:
        raise DataFileError("The file is empty: " + path)

    for one_column in needed_columns:
        if one_column not in columns:
            raise DataFileError("File " + path + " is missing the column: " + one_column)

    return rows


def load_companies(path):
    rows = read_csv_file(path, ["name", "description"])
    company_names = []
    for row in rows:
        company_names.append(row["name"].strip())

    logging.info("Loaded %s companies", len(company_names))
    return company_names


def load_destinations(path):
    rows = read_csv_file(path, ["name"])
    destination_names = []
    for row in rows:
        destination_names.append(row["name"].strip())

    logging.info("Loaded %s destinations", len(destination_names))
    return destination_names


def load_profiles(path):
    try:
        with open(path, encoding="utf-8") as f:
            profiles = json.load(f)
    except FileNotFoundError:
        raise DataFileError("Could not find the file: " + path)
    except json.JSONDecodeError:
        raise DataFileError("The profile file is not valid json: " + path)

    for name in profiles:
        if profiles[name].get("preferred_time") not in TIME_PRESETS:
            raise DataFileError("Profile " + name + " has a bad preferred_time")

    return profiles


def check_row(row, companies, destinations):
    """Check one offer row and return an Offer object."""
    for col in COLUMNS:
        if row.get(col) is None or row[col].strip() == "":
            raise InvalidOfferError("missing value in column " + col)

    cleaned = {}
    for col in COLUMNS:
        cleaned[col] = row[col].strip()

    if not ID_PATTERN.match(cleaned["offer_id"]):
        raise InvalidOfferError("bad offer id '" + cleaned["offer_id"] + "'")
    if cleaned["company"] not in companies:
        raise InvalidOfferError("unknown company '" + cleaned["company"] + "'")
    if cleaned["destination"] not in destinations:
        raise InvalidOfferError("unknown destination '" + cleaned["destination"] + "'")

    try:
        price = float(cleaned["price"])
        transfers = int(cleaned["transfers"])
        luggage = int(cleaned["luggage_kg"])
        seats = int(cleaned["seats"])
        rating = float(cleaned["rating"])
    except ValueError:
        raise InvalidOfferError("a number field is not a number")

    if price <= 0:
        raise InvalidOfferError("price must be above 0, got " + str(price))
    if transfers < 0 or luggage < 0:
        raise InvalidOfferError("transfers/luggage cannot be negative")
    if seats <= 0:
        raise InvalidOfferError("no available seats")
    if rating < 1 or rating > 5:
        raise InvalidOfferError("rating must be between 1 and 5, got " + str(rating))

    try:
        depart_string = cleaned["date"] + " " + cleaned["departure"]
        arrive_string = cleaned["arrival_date"] + " " + cleaned["arrival"]
        departure = None
        arrival = None

        for fmt in DATE_FORMATS:
            try:
                departure = datetime.strptime(depart_string, fmt + " %H:%M")
                break
            except ValueError:
                pass

        if departure is None:
            raise ValueError

        for fmt in DATE_FORMATS:
            try:
                arrival = datetime.strptime(arrive_string, fmt + " %H:%M")
                break
            except ValueError:
                pass

        if arrival is None:
            raise ValueError
    except ValueError:
        raise InvalidOfferError("not a valid date/time: '" + cleaned["date"] + " " + cleaned["departure"] + "'")

    if arrival <= departure:
        raise InvalidOfferError("arrival is not after departure")

    changeable_text = cleaned["changeable"].lower()
    refundable_text = cleaned["refundable"].lower()
    if changeable_text not in ("yes", "no") or refundable_text not in ("yes", "no"):
        raise InvalidOfferError("changeable/refundable must be yes or no")

    offer = Offer(
        cleaned["offer_id"],
        cleaned["company"],
        cleaned["destination"],
        departure,
        arrival,
        price,
        transfers,
        luggage,
        changeable_text == "yes",
        refundable_text == "yes",
        seats,
        rating,
    )
    return offer


def load_offers(path, companies, destinations):
    """Returns a list of valid offers and a list of rejected rows."""
    rows = read_csv_file(path, COLUMNS)
    valid_offers = []
    rejected = []
    seen = set()

    for row in rows:
        try:
            offer = check_row(row, companies, destinations)
            if offer.offer_id in seen:
                raise InvalidOfferError("duplicate offer id " + offer.offer_id)
            seen.add(offer.offer_id)
            valid_offers.append(offer)
        except InvalidOfferError as error:
            rejected.append((row.get("offer_id"), str(error)))
            logging.warning("Rejected offer %s: %s", row.get("offer_id"), error)

    logging.info("Loaded %s valid offers, rejected %s", len(valid_offers), len(rejected))
    return valid_offers, rejected
