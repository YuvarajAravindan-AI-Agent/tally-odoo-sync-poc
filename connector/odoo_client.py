"""
Thin XML-RPC wrapper for Odoo Online (SaaS) Accounting.

IMPORTANT about auth on Odoo Online SaaS:
  SaaS blocks plain-password XML-RPC logins. You must use an API KEY:
  in Odoo -> top-right avatar -> Preferences -> Account Security ->
  "New API Key". Put that key in config as the password.
"""
import ssl
import xmlrpc.client


class OdooClient:
    def __init__(self, url, db, username, api_key):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.api_key = api_key
        ctx = ssl.create_default_context()
        self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", context=ctx)
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", context=ctx)
        self.uid = None

    def authenticate(self):
        self.uid = self._common.authenticate(self.db, self.username, self.api_key, {})
        if not self.uid:
            raise PermissionError(
                "Odoo authentication failed. On SaaS you must use an API key "
                "(Preferences -> Account Security -> New API Key), not your login password."
            )
        return self.uid

    def execute(self, model, method, *args, **kwargs):
        return self._models.execute_kw(
            self.db, self.uid, self.api_key, model, method, list(args), kwargs
        )

    # --- convenience helpers used by the mapper/sync ---

    def find_or_create_partner(self, name):
        ids = self.execute("res.partner", "search", [["name", "=", name]], limit=1)
        if ids:
            return ids[0]
        return self.execute("res.partner", "create", {"name": name})

    def move_exists(self, tally_guid):
        """Dedupe: has this Tally voucher already been synced? Uses the 'ref' field."""
        ids = self.execute(
            "account.move", "search",
            [["ref", "=", f"TALLY:{tally_guid}"]], limit=1,
        )
        return ids[0] if ids else None

    def create_move(self, vals):
        return self.execute("account.move", "create", vals)
