"""
Talks to a TallyPrime XML/HTTP gateway (real or the mock in mock_tally/).

Sends the standard "Export Data -> Voucher Register" request and parses the
voucher ENVELOPE that Tally returns into plain Python dicts. Nothing here is
mock-specific: point `host`/`port` at a real TallyPrime (ServerPort=9000) and
it behaves the same.
"""
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class LedgerEntry:
    name: str
    deemed_positive: bool
    amount: float  # signed, as Tally reports it


@dataclass
class Voucher:
    guid: str
    vchtype: str
    number: str
    date: str  # YYYYMMDD as Tally stores it
    party: str
    narration: str
    ledgers: list = field(default_factory=list)


def _export_request(company, from_date, to_date):
    return (
        "<ENVELOPE>"
        "<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>"
        "<BODY><EXPORTDATA><REQUESTDESC>"
        "<REPORTNAME>Voucher Register</REPORTNAME>"
        "<STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        f"<SVFROMDATE>{from_date}</SVFROMDATE>"
        f"<SVTODATE>{to_date}</SVTODATE>"
        f"<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>"
        "</STATICVARIABLES>"
        "</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"
    )


class TallyClient:
    def __init__(self, host="127.0.0.1", port=9000, company="", timeout=30):
        self.url = f"http://{host}:{port}"
        self.company = company
        self.timeout = timeout

    def fetch_vouchers(self, from_date, to_date):
        req_xml = _export_request(self.company, from_date, to_date).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=req_xml, headers={"Content-Type": "text/xml"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        return self._parse(raw)

    @staticmethod
    def _parse(xml_text):
        # Tally XML is often not perfectly namespaced; ET handles our shape fine.
        root = ET.fromstring(xml_text)
        vouchers = []
        for v in root.iter("VOUCHER"):
            def text(tag, default=""):
                el = v.find(tag)
                return el.text if el is not None and el.text is not None else default

            ledgers = []
            for le in v.findall("ALLLEDGERENTRIES.LIST"):
                name_el = le.find("LEDGERNAME")
                amt_el = le.find("AMOUNT")
                dp_el = le.find("ISDEEMEDPOSITIVE")
                if name_el is None or amt_el is None:
                    continue
                ledgers.append(
                    LedgerEntry(
                        name=(name_el.text or "").strip(),
                        deemed_positive=(dp_el is not None and (dp_el.text or "").strip().lower() == "yes"),
                        amount=float(amt_el.text or 0),
                    )
                )
            vouchers.append(
                Voucher(
                    guid=text("GUID"),
                    vchtype=text("VOUCHERTYPENAME") or v.get("VCHTYPE", ""),
                    number=text("VOUCHERNUMBER"),
                    date=text("DATE"),
                    party=text("PARTYLEDGERNAME"),
                    narration=text("NARRATION"),
                    ledgers=ledgers,
                )
            )
        return vouchers
