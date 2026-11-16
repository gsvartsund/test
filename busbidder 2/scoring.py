from errors import WeightError

CRITERIA = {}


def criterion(name):
    def decorator(function):
        CRITERIA[name] = function
        return function
    return decorator


DEFAULT_WEIGHTS = {
    "price": 0.35,
    "duration": 0.25,
    "departure_time": 0.15,
    "flexibility": 0.15,
    "transfers": 0.10,
}

def lower_is_better(value, lowest, highest):
    if highest == lowest:
        return 100.0
    return 100.0 * (highest - value) / (highest - lowest)


@criterion("price")
def price_score(offer, request, offers):
    all_prices = [o.price for o in offers]
    return lower_is_better(offer.price, min(all_prices), max(all_prices))


@criterion("duration")
def duration_score(offer, request, offers):
    all_times = [o.duration_minutes() for o in offers]
    return lower_is_better(offer.duration_minutes(), min(all_times), max(all_times))


@criterion("departure_time")
def departure_time_score(offer, request, offers):
    minutes = offer.departure.hour * 60 + offer.departure.minute
    diff = abs(minutes - request.preferred_minutes())
    if diff > 720:
        diff = 1440 - diff
    return max(0, 100 - diff / 360 * 100)


@criterion("flexibility")
def flexibility_score(offer, request, offers):
    score = 0
    if offer.changeable:
        score += 60
    if offer.refundable:
        score += 40
    return float(score)


@criterion("transfers")
def transfers_score(offer, request, offers):
    if offer.transfers == 0:
        return 100.0
    if offer.transfers == 1:
        return 50.0
    return 0.0


def check_weights(weights):
    """Check weights, reject bad ones, then scale them to total 1."""
    total = 0
    for name in weights:
        if name not in CRITERIA:
            raise WeightError("Unknown criterion: " + name)
        if weights[name] < 0:
            raise WeightError("Weight for " + name + " cannot be negative")
        total += weights[name]

    if total <= 0:
        raise WeightError("The weights must add up to more than 0")

    fixed = {}
    for name in CRITERIA:
        fixed[name] = weights.get(name, 0) / total
    return fixed


def rank_offers(offers, request):
    """Return a list of (offer, scores, total), sorted best first."""
    weights = check_weights(request.weights)
    sorted_list = []

    for offer in offers:
        score_dict = {}
        total = 0
        for name in CRITERIA:
            score_value = CRITERIA[name](offer, request, offers)
            score_dict[name] = score_value
            total += weights[name] * score_value
        sorted_list.append((offer, score_dict, total))

    sorted_list.sort(key=lambda item: (-round(item[2], 6), item[0].price, item[0].offer_id))
    return sorted_list


def format_minutes(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return str(hours) + "h " + str(mins) + "m"


def explain(best, ranked, request):
    offer, scores, total = best
    average_price = sum(x[0].price for x in ranked) / len(ranked)
    good = []
    bad = []

    if offer.transfers == 0:
        good.append("it is a direct route")
    else:
        bad.append("it has " + str(offer.transfers) + " transfer(s)")

    if scores["departure_time"] >= 80:
        good.append("it leaves close to your preferred " + request.preferred_time + " time")
    elif scores["departure_time"] < 50:
        bad.append("it leaves quite far from your preferred " + request.preferred_time + " time")

    if offer.changeable and offer.refundable:
        good.append("the ticket is changeable and refundable")
    elif offer.changeable:
        good.append("the ticket can be changed")
    else:
        bad.append("the ticket cannot be changed")

    price_text = "the price (" + str(round(offer.price, 2)) + " EUR) is "
    if offer.price <= average_price:
        good.append(price_text + "below the average of " + str(round(average_price, 2)) + " EUR")
    else:
        bad.append(price_text + "above the average of " + str(round(average_price, 2)) + " EUR")

    if scores["duration"] < 50:
        bad.append("the journey (" + format_minutes(offer.duration_minutes()) + ") is slower than many other offers")

    text = "Offer " + offer.offer_id + " (" + offer.company + ") ranks first with " + str(round(total, 1)) + " points"
    if good:
        text += " because " + ", ".join(good)
    text += "."
    if bad:
        text += " Disadvantages: " + ", ".join(bad) + "."
    text += " This is only the best under your chosen constraints, weights and scoring rules, not the objectively best."
    return text
