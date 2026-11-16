import logging
import os
from datetime import datetime, timedelta

from errors import BusBidderError, BookingError, WeightError
from loader import load_companies, load_destinations, load_offers, load_profiles
from filters import filter_offers
from scoring import rank_offers, explain, check_weights, format_minutes, DEFAULT_WEIGHTS, CRITERIA
from booking import load_bookings, apply_bookings, create_booking
from models import Request, TIME_PRESETS

BASE = os.path.dirname(os.path.abspath(__file__))
BOOKINGS_FILE = os.path.join(BASE, "bookings.csv")
LOG_FILE = os.path.join(BASE, "busbidder.log")
DATE_FORMAT = "%d.%m.%Y"


def format_date(value):
    return value.strftime(DATE_FORMAT)

def ask(question, default):
    answer = input(question + " (for example: " + str(default) + "): ").strip()
    if answer == "":
        return default
    return answer

def ask_number(question, default):
    while True:
        try:
            value = float(ask(question, default))
            return value
        except ValueError:
            print("type a number")

def ask_date(question, default):
    while True:
        try:
            date_string = ask(question + " (DD.MM.YYYY)", default)
            parsed_date = datetime.strptime(date_string, DATE_FORMAT).date()
            if parsed_date < datetime.today().date():
                print("date cannot be in the past")
                continue
            return parsed_date
        except ValueError:
            print("use DD.MM.YYYY, for example 19.12.2026")

def ask_yes_no(question, default):
    while True:
        answer = ask(question + " (yes/no)", default).lower()
        if answer in ("yes", "y"):
            return True
        if answer in ("no", "n"):
            return False
        print("type yes or no or y/n")

def ask_trip(destinations):
    """destination and dates"""
    while True:
        answer = ask("Choose a city or type 'list' to see all", "Malaga")
        if answer.lower() == "list":
            print("  " + ", ".join(destinations))
            continue

        matches = []
        for item in destinations:
            if item.lower() == answer.lower():
                matches.append(item)

        if matches:
            chosen = matches[0]
            break

        print("Unknown destination")

    today = datetime.today().date()
    start_date = ask_date("Earliest travel date", format_date(today))
    end_date = ask_date("Latest travel date", format_date(today + timedelta(days=2)))
    return chosen, start_date, end_date

def build_custom_request(destinations):
    print("\nEnter the details for your trip, price, transfers, changebale ticket and minimum luggage")
    destination, start_date, end_date = ask_trip(destinations)
    max_budget = ask_number("Maximum price in EUR", 50)
    transfer_limit = int(ask_number("Maximum number of transfers", 1))
    must_be_changeable = ask_yes_no("Must the ticket be changeable?", "no")
    minimum_luggage = int(ask_number("Minimum luggage allowance in kg [number]", 0))

    while True:
        preferred_time = ask("Preferred departure: (morning/afternoon/evening/night)", "morning").lower()
        if preferred_time in TIME_PRESETS:
            break
        print("choose morning, afternoon, evening or night")

    weights = dict(DEFAULT_WEIGHTS)
    use_default = ask_yes_no("Use the default importance of each critiera?", "yes")
    if not use_default:
        print("Give each critera an importance from 0 to 100.")
        weights = {}
        for name in CRITERIA:
            weights[name] = ask_number("  Importance of " + name, int(DEFAULT_WEIGHTS[name] * 100))

        try:
            check_weights(weights)
        except WeightError as error:
            print("  Problem with the weights: " + str(error) + ". Using default weights.")
            weights = dict(DEFAULT_WEIGHTS)

    request = Request(
        "you",
        destination,
        start_date,
        end_date,
        max_budget,
        preferred_time,
        transfer_limit,
        must_be_changeable,
        minimum_luggage,
        weights,
    )
    return request

def profile_request(name, profile_data, destination, start_date, end_date):
    return Request(
        name,
        destination,
        start_date,
        end_date,
        profile_data["max_budget"],
        profile_data["preferred_time"],
        profile_data["max_transfers"],
        profile_data["need_changeable"],
        profile_data["min_luggage"],
        profile_data["weights"],
    )

def show_request(request):
    weights = check_weights(request.weights)
    print("\n=== Search for: " + request.name + " ===")
    print("Hard constraints (offer that differ are removed):")
    print("  destination: " + request.destination)
    print("  travel dates: " + format_date(request.start_date) + " to " + format_date(request.end_date))
    print("  max price: " + str(request.max_budget) + " EUR")
    print("  max transfers: " + str(request.max_transfers))
    print("  luggage at least: " + str(request.min_luggage) + " kg")
    print("  ticket must be changeable: " + ("yes" if request.need_changeable else "no"))
    print("  seats must be available")
    print("Soft preferences (these only change the score):")
    print("  preferred departure: " + request.preferred_time)

    bits = []
    for name in weights:
        bits.append(name + " " + str(round(weights[name] * 100)) + "%")
    print("  weights: " + ", ".join(bits))

def show_ranking(ranked, limit):
    print("\n#   ID      Company          Departs          Duration  Price  Transfers  Chg Ref  | Price Dur Time Flex Transfers | TOTAL")
    print("-" * 124)
    count = 1
    for offer, scores, total in ranked[:limit]:
        line = str(count).ljust(4)
        line += offer.offer_id.ljust(8)
        line += offer.company.ljust(17)
        line += offer.departure.strftime("%d %b %H:%M").ljust(17)
        line += format_minutes(offer.duration_minutes()).ljust(10)
        line += str(round(offer.price, 2)).ljust(7)
        line += str(offer.transfers).ljust(4)
        line += ("yes" if offer.changeable else "no").ljust(4)
        line += ("yes" if offer.refundable else "no").ljust(4)
        line += "| "
        line += str(round(scores["price"])).ljust(6)
        line += str(round(scores["duration"])).ljust(4)
        line += str(round(scores["departure_time"])).ljust(5)
        line += str(round(scores["flexibility"])).ljust(5)
        line += str(round(scores["transfers"])).ljust(6)
        line += "| " + str(round(total, 1))
        print(line)
        count += 1

def search_and_show(request, offers):
    show_request(request)
    accepted, removed = filter_offers(offers, request)

    print("\nRemoved by hard constraints (only offers for your destination and dates are counted):")
    shown = False
    for reason in removed:
        if reason not in ("wrong destination", "outside travel dates"):
            print("  " + str(removed[reason]) + " offer(s): " + reason)
            shown = True

    if not shown:
        print("  none")

    if len(accepted) == 0:
        print("\nNo offers match your hard constraints. Try a higher budget or more dates.")
        return []

    ranked = rank_offers(accepted, request)
    print("\n" + str(len(ranked)) + " acceptable offer(s), ranked:")
    limit = min(len(ranked), 10)
    if len(ranked) > 10:
        print("(showing the top 10)")

    show_ranking(ranked, limit)
    print("\n" + explain(ranked[0], ranked, request))
    return ranked[:limit]


def offer_booking(ranked, bookings):
    answer = input("\nType the # of the offer you want to buy: ").strip()
    if answer == "":
        return

    if not answer.isdigit() or int(answer) < 1 or int(answer) > len(ranked):
        print("Number does not exist in the list")
        return

    offer = ranked[int(answer) - 1][0]
    traveller_name = input("Name: ").strip()
    passengers = int(ask_number("Passengers:", 1))

    try:
        booking = create_booking(offer, traveller_name, passengers, bookings, BOOKINGS_FILE)
    except BookingError as error:
        print("Booking failed: " + str(error))
        return

    print("\nBooking completed :)")
    print(booking["ticket"])
    print("Traveller:   " + booking["traveller"] + " (" + str(booking["passengers"]) + " passenger(s))")
    print("Journey:     Madrid -> " + booking["destination"] + " with " + booking["company"])
    print("Departure:   " + booking["departure"])
    print("Total price: " + str(booking["total_price"]) + " EUR")
    print("Fare conditions: changeable=" + booking["changeable"] + ", refundable=" + booking["refundable"] + ", luggage=" + str(booking["luggage_kg"]) + " kg")
    print("Seats left on this offer: " + str(offer.seats))

def show_bookings(bookings):
    if len(bookings) == 0:
        print("\nError no bookings")
        return

    print("\nBookings:")
    for booking in bookings:
        print("  " + booking["ticket"] + " | " + booking["traveller"] + " | Madrid -> " + booking["destination"]
              + " | " + booking["departure"] + " | " + str(booking["passengers"]) + " pax | "
              + str(booking["total_price"]) + " EUR")

def use_profile(profiles, destinations, offers, bookings):
    names = list(profiles.keys())
    print("\nProfiles:")
    for i in range(len(names)):
        print("  " + str(i + 1) + ") " + names[i])

    choice = input("Choose a profile number: ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(names):
        print("Profile number dos not exist")
        return

    name = names[int(choice) - 1]
    destination, start_date, end_date = ask_trip(destinations)
    ranked = search_and_show(profile_request(name, profiles[name], destination, start_date, end_date), offers)
    if ranked:
        offer_booking(ranked, bookings)

def compare_profiles(profiles, destinations, offers):
    print("\nCompare traveller profiles on the same offers")
    destination, start_date, end_date = ask_trip(destinations)
    for name in profiles:
        search_and_show(profile_request(name, profiles[name], destination, start_date, end_date), offers)
        print("\n" + "#" * 112)

def main():
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Program started")

    try:
        companies = load_companies(os.path.join(BASE, "data", "companies.csv"))
        destinations = load_destinations(os.path.join(BASE, "data", "destinations.csv"))
        offers, rejected = load_offers(os.path.join(BASE, "data", "offers.csv"), companies, destinations)
        profiles = load_profiles(os.path.join(BASE, "data", "profiles.json"))
        bookings = load_bookings(BOOKINGS_FILE)
    except BusBidderError as error:
        print("Could not start: " + str(error))
        logging.error("Could not start: " + str(error))
        return

    apply_bookings(offers, bookings)
    print("Program started")
    print("Loaded " + str(len(offers)) + " valid offers. " + str(len(rejected)) + " invalid row(s) were rejected (see busbidder.log).")

    while True:
        print("\nOptions:")
        print("1) Trip search")
        print("2) Search with traveller profile")
        print("3) Compare profles")
        print("4) My bookings")
        print("5) Quit")
        choice = input("Choose 1-5: ").strip()

        if choice == "1":
            ranked = search_and_show(build_custom_request(destinations), offers)
            if ranked:
                offer_booking(ranked, bookings)
        elif choice == "2":
            use_profile(profiles, destinations, offers, bookings)
        elif choice == "3":
            compare_profiles(profiles, destinations, offers)
        elif choice == "4":
            show_bookings(bookings)
        elif choice == "5":
            print("Bye :()")
            logging.info("Program ended")
            break
        else:
            print("Please type a number from 1 to 5.")

if __name__ == "__main__":
    main()
