class BusBidderError(Exception):
    """Error for application"""
    pass


class DataFileError(BusBidderError):
    """The csv file or json is not working"""
    pass


class InvalidOfferError(BusBidderError):
    """A row in offers.csv is invalid"""
    pass


class WeightError(BusBidderError):
    """A score weight is bad"""
    pass


class BookingError(BusBidderError):
    """Booking cannot be created"""
    pass
