def first_broken_rule(offer, request):
    """Return the first rule that breaks, or None if the offer is fine."""
    if offer.destination != request.destination:
        return "wrong destination"

    if offer.departure.date() < request.start_date or offer.departure.date() > request.end_date:
        return "outside travel dates"

    if offer.seats < 1:
        return "no seats left"

    if offer.price > request.max_budget:
        return "over budget"

    if offer.transfers > request.max_transfers:
        return "too many transfers"

    if offer.luggage_kg < request.min_luggage:
        return "not enough luggage allowance"

    if request.need_changeable and not offer.changeable:
        return "ticket not changeable"

    return None


def filter_offers(offers, request):
    """Return accepted offers and a count for each reason they were removed."""
    accepted = []
    removed = {}

    for offer in offers:
        reason = first_broken_rule(offer, request)
        if reason is None:
            accepted.append(offer)
        else:
            if reason in removed:
                removed[reason] = removed[reason] + 1
            else:
                removed[reason] = 1

    return accepted, removed
