#to run: python -m unittest discover tests -v. Or run this file in IDE
import os
import sys
import tempfile
import unittest
from datetime import datetime, date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import ask, ask_date
from errors import DataFileError, InvalidOfferError, WeightError, BookingError
from models import Offer, Request
from loader import check_row, load_offers, read_csv_file
from filters import filter_offers, first_broken_rule
from scoring import CRITERIA, check_weights, rank_offers, lower_is_better, DEFAULT_WEIGHTS
from booking import create_booking, load_bookings, apply_bookings

COMPANIES = ["SolRuta", "Camino Express"]
DESTINATIONS = ["Malaga", "Toledo"]

def good_row():
    return {"offer_id": "OF0001", "company": "SolRuta", "destination": "Malaga",
            "date": "2026-07-12", "departure": "09:00", "arrival_date": "2026-07-12",
            "arrival": "17:00", "price": "40", "transfers": "0", "luggage_kg": "20",
            "changeable": "yes", "refundable": "no", "seats": "5", "rating": "4.0"}


def make_offer(offer_id="OF0001", price=40.0, hour=9, transfers=0, seats=5,
               changeable=True, refundable=False):
    dep = datetime(2026, 7, 12, hour, 0)
    arr = dep.replace(hour=min(23, hour + 8))
    return Offer(offer_id, "SolRuta", "Malaga", dep, arr, price, transfers, 20,
                 changeable, refundable, seats, 4.0)

def make_request(**changes):
    values = dict(name="test", destination="Malaga", start_date=date(2026, 7, 12),
                  end_date=date(2026, 7, 14), max_budget=50, preferred_time="morning",
                  max_transfers=1, need_changeable=False, min_luggage=0,
                  weights=dict(DEFAULT_WEIGHTS))
    values.update(changes)
    return Request(**values)

class TestLoading(unittest.TestCase):
    def test_normal_row(self):
        offer = check_row(good_row(), COMPANIES, DESTINATIONS)
        self.assertEqual(offer.duration_minutes(), 480)

    def test_generated_offer_id_format(self):
        row = good_row()
        row["offer_id"] = "Offer1"
        offer = check_row(row, COMPANIES, DESTINATIONS)
        self.assertEqual(offer.offer_id, "Offer1")

    def test_bad_values_rejected(self):
        # each pair is (column, bad value)
        bad = [("price", "-5"), ("destination", "Paris"), ("arrival", "08:00"),
               ("date", "2026-13-45"), ("rating", "7"), ("seats", "0"),
               ("offer_id", "BAD1"), ("offer_id", "of0001"), ("price", ""), ("price", "abc")]
        for column, value in bad:
            row = good_row()
            row[column] = value
            with self.assertRaises(InvalidOfferError):
                check_row(row, COMPANIES, DESTINATIONS)

    def test_rating_boundaries_ok(self):
        for rating in ["1", "5"]:
            row = good_row()
            row["rating"] = rating
            check_row(row, COMPANIES, DESTINATIONS)

    def test_missing_file(self):
        with self.assertRaises(DataFileError):
            read_csv_file("no_such_file.csv", ["name"])

    def test_missing_column(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "x.csv")
            with open(path, "w") as f:
                f.write("name\nA\n")
            with self.assertRaises(DataFileError):
                read_csv_file(path, ["name", "description"])

    def test_bad_rows_and_duplicates_skipped(self):
        header = "offer_id,company,destination,date,departure,arrival_date,arrival,price,transfers,luggage_kg,changeable,refundable,seats,rating\n"
        good = "OF0001,SolRuta,Malaga,2026-07-12,09:00,2026-07-12,17:00,40,0,20,yes,no,5,4.0\n"
        bad = "OF0002,SolRuta,Malaga,2026-07-12,09:00,2026-07-12,17:00,-1,0,20,yes,no,5,4.0\n"
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "offers.csv")
            with open(path, "w") as f:
                f.write(header + good + bad + good)
            offers, rejected = load_offers(path, COMPANIES, DESTINATIONS)
            self.assertEqual(len(offers), 1)
            self.assertEqual(len(rejected), 2)

class TestInput(unittest.TestCase):
    @patch("main.input", return_value="")
    def test_ask_shows_default_as_example(self, mock_input):
        self.assertEqual(ask("Choose a city", "Malaga"), "Malaga")
        mock_input.assert_called_once_with("Choose a city (for example: Malaga): ")

    @patch("main.input", side_effect=["12.202607", date.today().strftime("%d.%m.%Y")])
    def test_ask_date_rejects_wrong_order(self, _):
        self.assertEqual(ask_date("Earliest travel date", ""), date.today())

    @patch("main.input", side_effect=["01.01.2000", (date.today() + timedelta(days=1)).strftime("%d.%m.%Y")])
    def test_ask_date_rejects_past_date(self, _):
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(ask_date("Earliest travel date", ""), tomorrow)

class TestFilters(unittest.TestCase):
    def test_price_at_budget_ok(self):
        self.assertIsNone(first_broken_rule(make_offer(price=50.0), make_request()))

    def test_price_over_budget(self):
        self.assertEqual(first_broken_rule(make_offer(price=50.01), make_request()), "over budget")

    def test_transfers(self):
        self.assertEqual(first_broken_rule(make_offer(transfers=2), make_request()), "too many transfers")

    def test_changeable_required(self):
        r = make_request(need_changeable=True)
        self.assertEqual(first_broken_rule(make_offer(changeable=False), r), "ticket not changeable")

    def test_outside_dates(self):
        r = make_request(start_date=date(2026, 7, 13))
        self.assertEqual(first_broken_rule(make_offer(), r), "outside travel dates")

    def test_counts(self):
        accepted, removed = filter_offers([make_offer("OF0001", price=30), make_offer("OF0002", price=90)], make_request())
        self.assertEqual(len(accepted), 1)
        self.assertEqual(removed["over budget"], 1)

class TestScoring(unittest.TestCase):
    def test_criteria_registered(self):
        self.assertGreaterEqual(len(CRITERIA), 4)

    def test_lower_is_better(self):
        self.assertEqual(lower_is_better(10, 10, 50), 100)
        self.assertEqual(lower_is_better(50, 10, 50), 0)
        self.assertEqual(lower_is_better(20, 20, 20), 100)   # no divide by zero

    def test_weights_scaled(self):
        fixed = check_weights({"price": 50, "duration": 50})
        self.assertAlmostEqual(sum(fixed.values()), 1.0)

    def test_bad_weights(self):
        for w in [{"price": -1, "duration": 2}, {"price": 0}, {"colour": 1}]:
            with self.assertRaises(WeightError):
                check_weights(w)

    def test_different_weights_different_winner(self):
        cheap = make_offer("OF0001", price=30, changeable=False)
        flexible = make_offer("OF0002", price=45, refundable=True)
        self.assertEqual(rank_offers([cheap, flexible], make_request(weights={"price": 1}))[0][0].offer_id, "OF0001")
        self.assertEqual(rank_offers([cheap, flexible], make_request(weights={"flexibility": 1}))[0][0].offer_id, "OF0002")

    def test_tie_broken_by_price_then_id(self):
        ranked = rank_offers([make_offer("OF0002"), make_offer("OF0001")], make_request(weights={"flexibility": 1}))
        self.assertEqual(ranked[0][0].offer_id, "OF0001")

    def test_departure_wraps_midnight(self):
        offer = make_offer(hour=23)
        self.assertEqual(CRITERIA["departure_time"](offer, make_request(preferred_time="night"), [offer]), 100)


class TestBooking(unittest.TestCase):
    def test_booking_works(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "b.csv")
            offer = make_offer(seats=5)
            b = create_booking(offer, "Anna", 2, [], path)
            self.assertEqual(offer.seats, 3)
            self.assertEqual(b["ticket"], "Ticket 1")
            self.assertEqual(len(load_bookings(path)), 1)

    def test_all_seats_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            offer = make_offer(seats=2)
            create_booking(offer, "Anna", 2, [], os.path.join(folder, "b.csv"))
            self.assertEqual(offer.seats, 0)

    def test_booking_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "b.csv")
            for offer, name, n in [(make_offer(seats=1), "Anna", 2), (make_offer(), "  ", 1), (make_offer(), "A", 0)]:
                with self.assertRaises(BookingError):
                    create_booking(offer, name, n, [], path)

    def test_sequential_ticket_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            bookings = []
            offer = make_offer(seats=9)
            tickets = [create_booking(offer, "A", 1, bookings, os.path.join(folder, "b.csv"))["ticket"] for i in range(9)]
            self.assertEqual(tickets, ["Ticket " + str(i) for i in range(1, 10)])

    def test_seats_reduced_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "b.csv")
            create_booking(make_offer(seats=5), "Anna", 3, [], path)
            fresh = make_offer(seats=5)
            apply_bookings([fresh], load_bookings(path))
            self.assertEqual(fresh.seats, 2)

if __name__ == "__main__":
    unittest.main()
