TIME_PRESETS = {
    "morning": 9 * 60,
    "afternoon": 15 * 60,
    "evening": 20 * 60,
    "night": 23 * 60,
}


class Offer:
    def __init__(self, offer_id, company, destination, departure, arrival,
                 price, transfers, luggage_kg, changeable, refundable, seats, rating):
        self.offer_id = offer_id
        self.company = company
        self.destination = destination
        self.departure = departure
        self.arrival = arrival
        self.price = price
        self.transfers = transfers
        self.luggage_kg = luggage_kg
        self.changeable = changeable
        self.refundable = refundable
        self.seats = seats
        self.rating = rating

    def duration_minutes(self):
        # difference between arrival and departure in minutes
        time_in_seconds = (self.arrival - self.departure).total_seconds()
        return int(time_in_seconds // 60)


class Request:
    def __init__(self, name, destination, start_date, end_date, max_budget,
                 preferred_time, max_transfers, need_changeable, min_luggage, weights):
        self.name = name
        self.destination = destination
        self.start_date = start_date
        self.end_date = end_date
        self.max_budget = max_budget
        self.max_transfers = max_transfers
        self.need_changeable = need_changeable
        self.min_luggage = min_luggage
        self.preferred_time = preferred_time
        self.weights = weights

    def preferred_minutes(self):
        return TIME_PRESETS[self.preferred_time]
