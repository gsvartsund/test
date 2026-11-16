import csv
import logging
import os

from errors import BookingError

COLUMNS = [
    "ticket", "traveller", "offer_id", "company", "destination", "departure",
    "passengers", "total_price", "changeable", "refundable", "luggage_kg"
]

def load_bookings(path):
    if not os.path.exists(path):
        return []

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows

def apply_bookings(offers, bookings):
    """When the program starts again, remove the booked seats from the offer again."""
    for booking in bookings:
        for offer in offers:
            if offer.offer_id == booking["offer_id"]:
                offer.seats -= int(booking["passengers"])
                break

def make_ticket(bookings):
    return "Ticket " + str(len(bookings) + 1)

def create_booking(offer, traveller_name, passengers, bookings, path):
    name = traveller_name.strip()

    if name == "":
        raise BookingError("Please enter a name.")
    if passengers < 1 or passengers > 9:
        raise BookingError("You can book between 1 and 9 passengers.")
    if offer.seats < passengers:
        raise BookingError("Not enough seats left. Only " + str(offer.seats) + " available.")

    ticket = make_ticket(bookings)
    offer.seats -= passengers

    booking = {
        "ticket": ticket,
        "traveller": name,
        "offer_id": offer.offer_id,
        "company": offer.company,
        "destination": offer.destination,
        "departure": offer.departure.strftime("%m.%d.%Y %H:%M"),
        "passengers": passengers,
        "total_price": round(offer.price * passengers, 2),
        "changeable": "yes" if offer.changeable else "no",
        "refundable": "yes" if offer.refundable else "no",
        "luggage_kg": offer.luggage_kg,
    }

    is_new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(booking)

    bookings.append(booking)
    logging.info("Booking %s created for offer %s", ticket, offer.offer_id)
    return booking
