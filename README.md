# Tally → Odoo Accounting Sync (POC)

Feeds accounting vouchers entered in **TallyPrime (local)** into **Odoo Online
SaaS Accounting** (`ai-agentic-accounting.odoo.com`, saas~19.4+e). Sales →
Customer Invoice, Purchase → Vendor Bill. Financial side only (no Inventory).

## Why a mock Tally?

TallyPrime is a protected Windows binary; under Wine on this Ubuntu laptop its
anti-tamper self-check crashes at startup (a Wine/protector incompatibility, not
a config problem). Production runs Tally on real Windows, where the gateway works
normally. So `mock_tally/gateway.py` reproduces Tally's XML/HTTP gateway on
port 9000, letting the connector be built and tested now. Nothing in the
connector is mock-specific — point it at a real TallyPrime and it works unchanged.

## Layout

    mock_tally/gateway.py   Fake TallyPrime gateway on :9000 (dev only)
    connector/tally_client.py  Sends Voucher-Register export, parses voucher XML
    connector/odoo_client.py   Odoo XML-RPC wrapper (auth, partners, moves)
    connector/mapper.py        Tally voucher -> Odoo account.move fields
    connector/sync.py          Orchestrator: fetch -> dedupe -> create in Odoo
    config.example.yaml        Copy to config.yaml, add your Odoo API key

## Setup

1. **Odoo API key** (required — SaaS blocks password XML-RPC):
   In Odoo: avatar (top-right) → *Preferences* → *Account Security* →
   *New API Key*. Copy it.
2. `cp config.example.yaml config.yaml` and paste the key into `odoo.api_key`.
   (`config.yaml` is gitignored.)

## Run (against the mock)

    # terminal 1 — fake Tally
    python3 mock_tally/gateway.py

    # terminal 2 — one sync pass
    python3 connector/sync.py --once

    # or near-real-time polling every 10s
    python3 connector/sync.py --watch 10

Dedupe: each Odoo move stores `ref = TALLY:<voucher GUID>`. Re-running never
creates duplicates — already-synced vouchers are detected and skipped.

## Pointing at the real Tally (production)

In `config.yaml` set `tally.host`/`tally.port` to the Windows box running
TallyPrime (ensure `tally.ini` has `ServerPort = 9000` and the company is
loaded). No code changes.

## True real-time (vs. the poller here)

The `--watch` poller is "near real-time" (bounded by the poll interval). For
*immediate* push on voucher save, the production design adds a small **TDL**
(Tally Definition Language) script on the Tally side that fires on voucher
accept and POSTs the voucher to a webhook endpoint, which then calls the same
`mapper` + `odoo_client` code path. The poller remains as a safety-net/backfill.

## Scope / phase 2

- Receipt/Payment vouchers are parsed and classified but not yet posted — in
  Odoo they belong on `account.payment` and normally reconcile against an
  existing invoice. That's the next phase.
- Tax lines are currently folded into the invoice total. Mapping Tally GST
  ledgers to Odoo tax codes is a refinement for once the pipeline is signed off.
