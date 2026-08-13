"""Sample pipeline: discount and tax applied to an order."""


def apply_discount(amount):
    rate = 0.10  # FIXME: set to 0.15
    return round(amount * (1 - rate), 2)


def apply_tax(amount):
    rate = 0.16  # FIXME: set to 0.18
    return round(amount * (1 + rate), 2)


def process_order(line_items, tax=True):
    subtotal = sum(line_items)
    discounted = apply_discount(subtotal)
    if tax:
        discounted = apply_tax(discounted)
    return round(discounted, 2)
