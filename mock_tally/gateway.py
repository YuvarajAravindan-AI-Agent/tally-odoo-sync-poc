"""
Mock Tally Prime XML/HTTP gateway.

Simulates the gateway that real TallyPrime exposes on ServerPort=9000
(see tally.ini). It understands a "Export Data / Voucher Register" request
and replies with voucher XML in the same shape TallyPrime produces, so the
connector can be developed and tested without the TallyPrime GUI running.

Run:  python3 mock_tally/gateway.py           # listens on 127.0.0.1:9000
Swap for the real thing later by pointing the connector at the real Tally
host:port — no connector code changes required.
"""
import datetime as dt
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 9000

# A tiny in-memory "day book". Each entry mimics one TallyPrime voucher.
# GUID is Tally's stable unique id — the connector uses it to dedupe.
_VOUCHERS = [
    {
        "guid": "6f0b7e2a-0001-4c9a-9f01-000000000001",
        "vchtype": "Sales",
        "number": "S/001",
        "date": "20260715",
        "party": "ABC Traders",
        "narration": "Sale of goods",
        "ledgers": [
            {"name": "ABC Traders", "deemed_positive": "Yes", "amount": -11800.00},
            {"name": "Sales Account", "deemed_positive": "No", "amount": 10000.00},
            {"name": "Output CGST", "deemed_positive": "No", "amount": 900.00},
            {"name": "Output SGST", "deemed_positive": "No", "amount": 900.00},
        ],
    },
    {
        "guid": "6f0b7e2a-0002-4c9a-9f01-000000000002",
        "vchtype": "Purchase",
        "number": "P/001",
        "date": "20260715",
        "party": "XYZ Suppliers",
        "narration": "Purchase of raw material",
        "ledgers": [
            {"name": "XYZ Suppliers", "deemed_positive": "No", "amount": 5900.00},
            {"name": "Purchase Account", "deemed_positive": "Yes", "amount": -5000.00},
            {"name": "Input CGST", "deemed_positive": "Yes", "amount": -450.00},
            {"name": "Input SGST", "deemed_positive": "Yes", "amount": -450.00},
        ],
    },
    {
        "guid": "6f0b7e2a-0003-4c9a-9f01-000000000003",
        "vchtype": "Receipt",
        "number": "R/001",
        "date": "20260715",
        "party": "ABC Traders",
        "narration": "Payment received against S/001",
        "ledgers": [
            {"name": "Bank Account", "deemed_positive": "Yes", "amount": -11800.00},
            {"name": "ABC Traders", "deemed_positive": "No", "amount": 11800.00},
        ],
    },
    # --- fresh data added for the live demo ---
    {
        "guid": "6f0b7e2a-0004-4c9a-9f01-000000000004",
        "vchtype": "Sales",
        "number": "S/002",
        "date": "20260715",
        "party": "Global Enterprises Pvt Ltd",
        "narration": "Sale of finished goods - demo",
        "ledgers": [
            {"name": "Global Enterprises Pvt Ltd", "deemed_positive": "Yes", "amount": -47200.00},
            {"name": "Sales Account", "deemed_positive": "No", "amount": 40000.00},
            {"name": "Output CGST", "deemed_positive": "No", "amount": 3600.00},
            {"name": "Output SGST", "deemed_positive": "No", "amount": 3600.00},
        ],
    },
    {
        "guid": "6f0b7e2a-0005-4c9a-9f01-000000000005",
        "vchtype": "Purchase",
        "number": "P/002",
        "date": "20260715",
        "party": "Sunrise Distributors",
        "narration": "Purchase of packaging material - demo",
        "ledgers": [
            {"name": "Sunrise Distributors", "deemed_positive": "No", "amount": 23600.00},
            {"name": "Purchase Account", "deemed_positive": "Yes", "amount": -20000.00},
            {"name": "Input CGST", "deemed_positive": "Yes", "amount": -1800.00},
            {"name": "Input SGST", "deemed_positive": "Yes", "amount": -1800.00},
        ],
    },
]


def _voucher_xml(v):
    parts = [
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">',
        f'<VOUCHER VCHTYPE="{v["vchtype"]}" ACTION="Create">',
        f"<DATE>{v['date']}</DATE>",
        f"<VOUCHERTYPENAME>{v['vchtype']}</VOUCHERTYPENAME>",
        f"<VOUCHERNUMBER>{v['number']}</VOUCHERNUMBER>",
        f"<PARTYLEDGERNAME>{v['party']}</PARTYLEDGERNAME>",
        f"<NARRATION>{v['narration']}</NARRATION>",
        f"<GUID>{v['guid']}</GUID>",
    ]
    for led in v["ledgers"]:
        parts += [
            "<ALLLEDGERENTRIES.LIST>",
            f"<LEDGERNAME>{led['name']}</LEDGERNAME>",
            f"<ISDEEMEDPOSITIVE>{led['deemed_positive']}</ISDEEMEDPOSITIVE>",
            f"<AMOUNT>{led['amount']:.2f}</AMOUNT>",
            "</ALLLEDGERENTRIES.LIST>",
        ]
    parts += ["</VOUCHER>", "</TALLYMESSAGE>"]
    return "".join(parts)


def build_response(from_date=None, to_date=None):
    """Return the full ENVELOPE Tally would send for a Voucher Register export."""
    selected = _VOUCHERS
    if from_date or to_date:
        def in_range(d):
            lo = from_date or "00000000"
            hi = to_date or "99999999"
            return lo <= d <= hi
        selected = [v for v in _VOUCHERS if in_range(v["date"])]
    body = "".join(_voucher_xml(v) for v in selected)
    return (
        "<ENVELOPE><HEADER><VERSION>1</VERSION>"
        "<STATUS>1</STATUS></HEADER>"
        f"<BODY><DATA>{body}</DATA></BODY></ENVELOPE>"
    )


def _extract_dates(request_xml):
    try:
        root = ET.fromstring(request_xml)
    except ET.ParseError:
        return None, None
    fd = root.find(".//SVFROMDATE")
    td = root.find(".//SVTODATE")
    return (fd.text if fd is not None else None, td.text if td is not None else None)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        request_xml = self.rfile.read(length).decode("utf-8", "replace")
        from_date, to_date = _extract_dates(request_xml)
        response = build_response(from_date, to_date)
        payload = response.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # Tally clients sometimes probe with GET; answer politely.
    def do_GET(self):
        payload = b"TallyPrime Server is Running (mock)"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[mock-tally] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[mock-tally] listening on http://{HOST}:{PORT}  ({len(_VOUCHERS)} vouchers)")
    print(f"[mock-tally] started {dt.datetime.now().isoformat(timespec='seconds')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock-tally] stopped")
