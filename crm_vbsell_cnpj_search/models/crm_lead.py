# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

import requests

from odoo import Command, models

from odoo.addons.crm_vbsell.const import REQUEST_TIMEOUT

_logger = logging.getLogger(__name__)

# cnpj_cpf is computed from vat, which the contact already carries.
# provider_name belongs to the search wizard, not to the partner.
_SKIP_CNPJ_KEYS = {"cnpj_cpf", "provider_name"}


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def _vbsell_company_and_contact(self, company, contact):
        person = super()._vbsell_company_and_contact(company, contact)
        self._vbsell_enrich_cnpj_company(company, person.parent_id, contact)
        return person

    def _vbsell_enrich_cnpj_company(self, company, company_partner, contact):
        """Fill the company from the registry without blocking the webhook.

        The lookup runs only when the company asked for it and the partner
        has no legal name yet. ReceitaWS allows three requests per minute, so
        a company that was already enriched is left alone. Any failure is
        logged and the lead keeps the company created from the VBSell contact.
        """
        if not company.vbsell_cnpj_search or not company_partner:
            return
        if company_partner.legal_name:
            return
        vat = self._vbsell_vat_digits(contact.get("vat"))
        if not vat:
            return
        try:
            values, shareholders = self._vbsell_cnpj_values(vat)
        except Exception:
            _logger.exception("VBSell CNPJ lookup failed for %s.", vat)
            return
        self._vbsell_apply_cnpj_company(company_partner, values)
        self._vbsell_attach_cnpj_shareholders(company, company_partner, shareholders)

    def _vbsell_cnpj_values(self, vat):
        """Call the provider configured on the Brazilian CNPJ search module."""
        webservice = self.env["l10n_br_cnpj_search.webservice.abstract"]
        url = webservice.get_api_url(vat)
        if not url:
            return {}, self.env["res.partner"]
        response = requests.get(
            url,
            headers=webservice.get_headers() or {},
            timeout=REQUEST_TIMEOUT,
        )
        data = webservice.validate(response)
        imported = webservice.import_data(data) or {}
        if not isinstance(imported, dict):
            return {}, self.env["res.partner"]
        for key in _SKIP_CNPJ_KEYS:
            imported.pop(key, None)
        return imported, self._vbsell_cnpj_shareholders(imported)

    def _vbsell_cnpj_shareholders(self, values):
        """Take SERPRO shareholders out of the company values.

        ``import_data`` creates those partners and returns ``child_ids`` as
        ``Command.set``. Writing that command would drop the VBSell person.
        """
        commands = values.pop("child_ids", None) or []
        partners = self.env["res.partner"]
        for command in commands:
            if not isinstance(command, (list, tuple)) or len(command) < 3:
                continue
            if command[0] != Command.SET:
                continue
            partners |= self.env["res.partner"].browse(command[2]).exists()
        return partners

    def _vbsell_apply_cnpj_company(self, company_partner, values):
        prepared = self._vbsell_prepare_cnpj_values(company_partner, values)
        if not prepared:
            return
        try:
            company_partner.with_context(
                disable_cpf_cnpj_validation=True,
                allow_vat_duplicate=True,
                no_vat_validation=True,
            ).write(prepared)
        except Exception:
            _logger.exception(
                "VBSell CNPJ data could not be saved on partner %s.",
                company_partner.id,
            )

    def _vbsell_prepare_cnpj_values(self, company_partner, values):
        prepared = {}
        for key, value in values.items():
            if key in _SKIP_CNPJ_KEYS or key not in company_partner._fields:
                continue
            field = company_partner._fields[key]
            if field.type == "one2many":
                continue
            if field.type == "many2many":
                command = self._vbsell_cnpj_many2many(value)
                if command:
                    prepared[key] = command
                continue
            if field.type == "many2one" and value and not isinstance(value, int):
                value = value.id
            if field.type in ("float", "monetary", "integer") and isinstance(
                value, str
            ):
                value = self._vbsell_cnpj_number(value)
                if field.type == "integer" and value is not None:
                    value = int(value)
            if value in (False, None, ""):
                continue
            prepared[key] = value
        if prepared and not company_partner.country_id:
            prepared["country_id"] = self.env.ref("base.br").id
        return prepared

    def _vbsell_cnpj_many2many(self, value):
        if not isinstance(value, list) or not value:
            return None
        if isinstance(value[0], (list, tuple)):
            return value
        ids = [item for item in value if isinstance(item, int)]
        if not ids:
            return None
        return [Command.set(ids)]

    def _vbsell_cnpj_number(self, value):
        text = value.strip()
        if not text:
            return None
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    def _vbsell_attach_cnpj_shareholders(self, company, company_partner, shareholders):
        loose = shareholders.filtered(lambda partner: not partner.parent_id)
        if not loose:
            return
        try:
            loose.with_context(
                disable_cpf_cnpj_validation=True,
                allow_vat_duplicate=True,
            ).write(
                {
                    "parent_id": company_partner.id,
                    "company_id": company.id,
                }
            )
        except Exception:
            _logger.exception(
                "VBSell CNPJ shareholders could not be linked to partner %s.",
                company_partner.id,
            )
