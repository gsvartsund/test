import csv
import os
import random
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
random.seed(10)

COMPANIES = [
    ("SolRuta", "Low-cost daytime services"),
    ("Camino Express", "Fast direct connections between major cities"),
    ("CostaLink", "Strong coverage of coastal destinations"),
    ("VerdeBus", "Environment-focused services and modern vehicles"),
    ("NocheVia", "Overnight and late-evening services"),
]
DESTINATIONS = [
    ("Barcelona", True), ("Valencia", True), ("Seville", False),
    ("Malaga", True), ("Granada", False), ("Cordoba", False),
    ("Bilbao", True), ("San Sebastian", True), ("Zaragoza", False),
    ("Alicante", True), ("Murcia", False), ("Salamanca", False),
    ("Toledo", False), ("Santiago de Compostela", False), ("Cadiz", True),
]
ROUTE_BASE = {
    "Barcelona": (220, 42), "Valencia": (155, 30), "Seville": (210, 34),
    "Malaga": (180, 32), "Granada": (170, 28), "Cordoba": (150, 26),
    "Bilbao": (195, 36), "San Sebastian": (185, 35), "Zaragoza": (140, 24),
    "Alicante": (165, 31), "Murcia": (145, 27), "Salamanca": (120, 21),
    "Toledo": (95, 18), "Santiago de Compostela": (240, 40), "Cadiz": (200, 39),
}
SETTINGS = {
    "SolRuta":        (60, 18, [8, 10, 14],  [0, 1, 2], 0.2, 0.05, 15, 3.5),
    "Camino Express": (85, 32, [7, 9, 16],   [0],       0.7, 0.4,  25, 4.3),
    "CostaLink":      (70, 24, [8, 11, 15],  [0, 1],    0.5, 0.2,  20, 4.0),
    "VerdeBus":       (72, 26, [9, 13, 17],  [0, 1],    0.6, 0.3,  20, 4.4),
    "NocheVia":       (68, 20, [21, 22, 23], [0, 1],    0.3, 0.1,  20, 3.8),
}
TODAY = datetime.today().date()
DAYS_AHEAD = 7
DEPARTURES_PER_DAY = 1
DATES = [(TODAY + timedelta(days=offset)).strftime("%d.%m.%Y") for offset in range(DAYS_AHEAD)]

HEADER = ["offer_id", "company", "destination", "date", "departure", "arrival_date",
          "arrival", "price", "transfers", "luggage_kg", "changeable", "refundable",
          "seats", "rating"]

rows = []
counter = 1

for company, description in COMPANIES:
    speed, base_price, hours, transfer_options, p_change, p_refund, luggage, base_rating = SETTINGS[company]
    for destination, coastal in DESTINATIONS:
        route_minutes, route_price = ROUTE_BASE[destination]
        for date in DATES:
            for hour in random.sample(hours, DEPARTURES_PER_DAY):
                minute = random.choice([0, 30])
                departure = datetime.strptime(date + " " + str(hour) + ":" + str(minute), "%d.%m.%Y %H:%M")
                transfers = random.choice(transfer_options)
                changeable = random.random() < p_change
                refundable = changeable and random.random() < p_refund * 2

                this_speed = speed
                this_price = base_price + route_price
                if coastal and company == "CostaLink":
                    this_speed = speed + 8             
                    this_price = this_price * 0.85

                duration = int(route_minutes / this_speed * 60 + transfers * 45 + random.randint(0, 20))
                price = this_price * random.uniform(0.9, 1.2)
                if changeable:
                    price = price + 6
                if refundable:
                    price = price + 8

                rating = round(min(5.0, max(1.0, base_rating + random.uniform(-0.4, 0.4))), 1)
                arrival = departure + timedelta(minutes=duration)

                rows.append([
                    "Offer" + str(counter), company, destination,
                    departure.strftime("%d.%m.%Y"), departure.strftime("%H:%M"),
                    arrival.strftime("%d.%m.%Y"), arrival.strftime("%H:%M"),
                    round(price, 2), transfers, luggage,
                    "yes" if changeable else "no", "yes" if refundable else "no",
                    random.randint(0, 30), rating,
                ])
                counter = counter + 1

regular_count = counter - 1
rows.append(["Offer" + str(counter), "SolRuta", "Malaga", "12.07.2026", "09:00", "12.07.2026", "17:00", -5, 0, 15, "no", "no", 10, 4.0])
counter += 1
rows.append(["Offer" + str(counter), "CostaLink", "Paris", "12.07.2026", "09:00", "12.07.2026", "17:00", 40, 0, 15, "no", "no", 10, 4.0])
counter += 1
rows.append(["Offer" + str(counter), "VerdeBus", "Malaga", "45.13.2026", "09:00", "12.07.2026", "17:00", 40, 0, 15, "no", "no", 10, 4.0])
counter += 1
rows.append(["Offer" + str(counter), "Camino Express", "Malaga", "12.07.2026", "18:00", "12.07.2026", "09:00", 40, 0, 15, "no", "no", 10, 4.0])

with open(os.path.join(BASE, "data", "offers.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(HEADER)
    writer.writerows(rows)

with open(os.path.join(BASE, "data", "companies.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "description"])
    writer.writerows(COMPANIES)

with open(os.path.join(BASE, "data", "destinations.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name"])
    for destination, coastal in DESTINATIONS:
        writer.writerow([destination])

print("Wrote", len(rows), "offers (", regular_count, "regular + 4 test rows )")