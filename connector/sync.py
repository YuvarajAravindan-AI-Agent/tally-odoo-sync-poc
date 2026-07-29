"""
Tally -> Odoo sync orchestrator.

Flow per cycle:
  1. Ask Tally (real gateway or mock) for vouchers in a date range.
  2. For each voucher: classify, skip if already synced (dedupe on GUID via ref).
  3. Map -> create the account.move in Odoo SaaS Accounting.

Two run modes:
  --once        one pass then exit (good for testing / cron).
  --watch N     poll every N seconds ("near real-time"). For TRUE real-time,
                the production design pushes from Tally via a TDL event trigger
                (see README) — this poller is the dev/fallback path.

Config comes from config.yaml (see config.example.yaml). No secrets in code.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mapper
from tally_client import TallyClient
from odoo_client import OdooClient


def _load_config(path):
    # Minimal YAML-ish loader (key: value, one level) to avoid a pyyaml dependency.
    cfg = {}
    section = cfg
    stack = [(0, cfg)]
    for raw in Path(path).read_text().splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key, _, val = raw.strip().partition(":")
        val = val.strip()
        # strip inline comments (unless the value is quoted)
        if val[:1] not in "\"'" and "#" in val:
            val = val.split("#", 1)[0].strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
        section = stack[-1][1]
        if val == "":
            new = {}
            section[key] = new
            stack.append((indent + 2, new))
        else:
            # strip quotes
            if val and val[0] in "\"'" and val[-1] == val[0]:
                val = val[1:-1]
            section[key] = val
    return cfg


def run_once(cfg, verbose=True):
    tally = TallyClient(
        host=cfg["tally"]["host"],
        port=int(cfg["tally"]["port"]),
        company=cfg["tally"].get("company", ""),
    )
    odoo = OdooClient(
        url=cfg["odoo"]["url"],
        db=cfg["odoo"]["db"],
        username=cfg["odoo"]["username"],
        api_key=cfg["odoo"]["api_key"],
    )
    odoo.authenticate()

    vouchers = tally.fetch_vouchers(
        cfg["sync"]["from_date"], cfg["sync"]["to_date"]
    )
    created, skipped, unsupported = 0, 0, 0
    for v in vouchers:
        kind = mapper.classify(v)
        if kind == "unsupported":
            unsupported += 1
            if verbose:
                print(f"  - {v.vchtype} {v.number}: unsupported voucher type, skipped")
            continue
        if kind == "payment":
            unsupported += 1
            if verbose:
                print(f"  - {v.vchtype} {v.number}: payment/receipt (phase 2), skipped")
            continue

        existing = odoo.move_exists(v.guid)
        if existing:
            skipped += 1
            if verbose:
                print(f"  - {v.vchtype} {v.number}: already synced (move id {existing})")
            continue

        partner_id = odoo.find_or_create_partner(v.party)
        vals = mapper.to_move_vals(v, partner_id)
        move_id = odoo.create_move(vals)
        created += 1
        if verbose:
            print(f"  + {v.vchtype} {v.number}: created Odoo move id {move_id} "
                  f"(partner '{v.party}', amount {mapper.invoice_line_amount(v):.2f})")

    print(f"[sync] done: {created} created, {skipped} already-synced, "
          f"{unsupported} skipped, of {len(vouchers)} fetched.")
    return created


def main():
    ap = argparse.ArgumentParser(description="Tally -> Odoo sync")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config.yaml"))
    ap.add_argument("--once", action="store_true", help="run one pass and exit")
    ap.add_argument("--watch", type=int, metavar="SECONDS",
                    help="poll every SECONDS (near real-time)")
    args = ap.parse_args()

    cfg = _load_config(args.config)

    if args.watch:
        print(f"[sync] watching every {args.watch}s (Ctrl-C to stop)")
        try:
            while True:
                run_once(cfg, verbose=True)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n[sync] stopped")
    else:
        run_once(cfg, verbose=True)


if __name__ == "__main__":
    main()
