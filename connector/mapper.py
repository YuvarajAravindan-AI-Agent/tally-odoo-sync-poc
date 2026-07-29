"""
Maps a parsed Tally Voucher -> Odoo account.move values.

Scope note (matches the agreed POC): we sync the FINANCIAL side only
(Sales -> Customer Invoice, Purchase -> Vendor Bill). Receipt/Payment
vouchers are recognised and reported but not posted as account.move here,
because in Odoo they belong on account.payment and normally reconcile against
an existing invoice — that's a second phase, not the first proof-of-pipeline.
"""

# Tally voucher type -> Odoo move_type
VCHTYPE_TO_MOVE = {
    "Sales": "out_invoice",
    "Credit Note": "out_refund",
    "Purchase": "in_invoice",
    "Debit Note": "in_refund",
}

PAYMENT_TYPES = {"Receipt", "Payment"}


def classify(voucher):
    """Return one of: 'invoice', 'payment', 'unsupported'."""
    if voucher.vchtype in VCHTYPE_TO_MOVE:
        return "invoice"
    if voucher.vchtype in PAYMENT_TYPES:
        return "payment"
    return "unsupported"


def _tally_date_to_odoo(d):
    # Tally: YYYYMMDD -> Odoo: YYYY-MM-DD
    if len(d) == 8 and d.isdigit():
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    return d


def invoice_line_amount(voucher):
    """
    Net revenue/expense amount for the invoice line, taken from the non-party
    ledgers. Tally stores amounts signed; we return a positive magnitude that
    Odoo expects on the invoice line price_unit.
    """
    party = voucher.party
    total = 0.0
    for led in voucher.ledgers:
        if led.name == party:
            continue
        total += abs(led.amount)
    return round(total, 2)


def to_move_vals(voucher, partner_id):
    move_type = VCHTYPE_TO_MOVE[voucher.vchtype]
    amount = invoice_line_amount(voucher)
    label = voucher.narration or f"{voucher.vchtype} {voucher.number}"
    return {
        "move_type": move_type,
        "partner_id": partner_id,
        "invoice_date": _tally_date_to_odoo(voucher.date),
        "ref": f"TALLY:{voucher.guid}",  # dedupe key + audit trail back to Tally
        "narration": f"Imported from Tally voucher {voucher.number} (GUID {voucher.guid})",
        "invoice_line_ids": [
            (0, 0, {
                "name": label,
                "quantity": 1,
                "price_unit": amount,
            })
        ],
    }
