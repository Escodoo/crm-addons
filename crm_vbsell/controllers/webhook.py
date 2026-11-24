# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hmac
import json
import logging
from hashlib import sha256

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


def signature_matches(secret, body, header):
    if not secret or not header or not header.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), body, sha256).hexdigest()
    provided = header.split("=", 1)[1].strip()
    if len(provided) != len(digest):
        return False
    return hmac.compare_digest(digest, provided)


class VbsellWebhook(http.Controller):
    @http.route(
        "/vbsell/webhook/opportunity",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def opportunity(self, **kwargs):
        raw = request.httprequest.get_data() or b""
        try:
            payload = json.loads(raw.decode() or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._response({"error": "Invalid JSON"}, 400)
        if not isinstance(payload, dict):
            return self._response({"error": "Invalid JSON"}, 400)
        company = self._company_for_payload(payload)
        if not company:
            return self._response({"error": "Company not found"}, 404)
        header = request.httprequest.headers.get("X-Webhook-Signature")
        if not signature_matches(company.vbsell_webhook_secret, raw, header):
            return self._response({"error": "Invalid signature"}, 401)
        try:
            with request.env.cr.savepoint():
                result = (
                    request.env["crm.lead"]
                    .sudo()
                    .with_company(company)
                    ._vbsell_apply_webhook(company, payload)
                )
        except UserError as error:
            return self._response({"error": error.args[0]}, 422)
        except Exception:
            _logger.exception("VBSell webhook failed")
            return self._response({"error": "Webhook processing failed"}, 500)
        return self._response(result, 200)

    def _company_for_payload(self, payload):
        opportunity = (payload.get("data") or {}).get("opportunity") or {}
        company_uuid = opportunity.get("companyId")
        if not company_uuid:
            return request.env["res.company"]
        return (
            request.env["res.company"]
            .sudo()
            .search(
                [
                    ("vbsell_company_uuid", "=", company_uuid),
                    ("vbsell_enabled", "=", True),
                ],
                limit=1,
            )
        )

    def _response(self, payload, status):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
