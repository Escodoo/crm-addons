# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from urllib.parse import quote

import requests

from odoo import _, models
from odoo.exceptions import UserError

from ..const import REQUEST_TIMEOUT


class VbsellApi(models.AbstractModel):
    _name = "vbsell.api"
    _description = "VBSell API Client"

    def _headers(self, company):
        return {
            "Authorization": f"Bearer {company.vbsell_api_key or ''}",
            "Accept": "application/json",
        }

    def _url(self, company, path):
        base = (company.vbsell_api_base_url or "").rstrip("/")
        return f"{base}{path}"

    def get_contact(self, company, contact_id):
        url = self._url(
            company,
            f"/api/v1/contacts/{quote(str(contact_id), safe='')}",
        )
        try:
            response = requests.get(
                url,
                headers=self._headers(company),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as error:
            raise UserError(
                _("VBSell contact request failed: %(error)s", error=error)
            ) from error
        if response.status_code >= 400:
            raise UserError(
                _(
                    "VBSell contact %(contact)s could not be fetched (%(status)s).",
                    contact=contact_id,
                    status=response.status_code,
                )
            )
        payload = response.json()
        contact = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(contact, dict):
            raise UserError(_("VBSell contact response is invalid."))
        return contact

    def patch_opportunity(self, company, opportunity_id, stage):
        url = self._url(
            company,
            f"/api/v1/opportunities/{quote(str(opportunity_id), safe='')}",
        )
        try:
            response = requests.patch(
                url,
                json={"stage": stage},
                headers=self._headers(company),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as error:
            raise UserError(
                _("VBSell stage update failed: %(error)s", error=error)
            ) from error
        if response.status_code >= 400:
            raise UserError(
                _(
                    "VBSell rejected the stage update (%(status)s).",
                    status=response.status_code,
                )
            )
        return True
