# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

import requests

from odoo import Command
from odoo.tests.common import TransactionCase


class TestVbsellCnpjSearch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "vbsell_enabled": True,
                "vbsell_company_uuid": "company-uuid",
                "vbsell_cnpj_search": False,
            }
        )
        cls.lead_model = cls.env["crm.lead"]

    def _contact(self, **overrides):
        contact = {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+55 11 99999-0000",
            # Checksum-valid, so the Brazilian localization accepts the
            # company once the lookup sets the country to Brazil.
            "vat": "00000000000191",
            "organizationName": "Chat Name",
            "jobTitle": "Analyst",
        }
        contact.update(overrides)
        return contact

    def _registry(self, **overrides):
        values = {
            "legal_name": "Analytical Engines Ltda",
            "name": "Analytical Engines",
            "street_name": "Rua Um",
            "email": "corp@example.com",
            "equity_capital": "1.500,00",
            "cnae_secondary_ids": [],
            "provider_name": "receitaws",
            "cnpj_cpf": "00000000000191",
        }
        values.update(overrides)
        return values

    def test_disabled_lookup_is_not_called(self):
        with patch.object(type(self.lead_model), "_vbsell_cnpj_values") as mocked:
            person = self.lead_model._vbsell_company_and_contact(
                self.company, self._contact()
            )
        mocked.assert_not_called()
        self.assertEqual(person.parent_id.name, "Chat Name")
        self.assertFalse(person.parent_id.legal_name)

    def test_lookup_fills_the_company_and_keeps_the_person(self):
        self.company.vbsell_cnpj_search = True
        with patch.object(
            type(self.lead_model),
            "_vbsell_cnpj_values",
            return_value=(self._registry(), self.env["res.partner"]),
        ):
            person = self.lead_model._vbsell_company_and_contact(
                self.company, self._contact()
            )
        company_partner = person.parent_id
        self.assertEqual(company_partner.legal_name, "Analytical Engines Ltda")
        self.assertEqual(company_partner.name, "Analytical Engines")
        self.assertEqual(company_partner.street_name, "Rua Um")
        self.assertEqual(company_partner.email, "corp@example.com")
        self.assertEqual(company_partner.equity_capital, 1500)
        self.assertEqual(company_partner.country_id, self.env.ref("base.br"))
        self.assertEqual(person.name, "Ada Lovelace")
        self.assertEqual(person.email, "ada@example.com")
        self.assertEqual(person.function, "Analyst")
        self.assertFalse(person.is_company)

    def test_company_with_legal_name_is_not_queried_again(self):
        self.company.vbsell_cnpj_search = True
        calls = []

        def fake(*args, **kwargs):
            calls.append(args[-1])
            return self._registry(), self.env["res.partner"]

        with patch.object(
            type(self.lead_model), "_vbsell_cnpj_values", side_effect=fake
        ):
            self.lead_model._vbsell_company_and_contact(self.company, self._contact())
            self.lead_model._vbsell_company_and_contact(
                self.company,
                self._contact(name="Grace Hopper", email="grace@example.com"),
            )
        self.assertEqual(calls, ["00000000000191"])

    def test_lookup_error_still_creates_the_contact(self):
        self.company.vbsell_cnpj_search = True
        with patch.object(
            type(self.lead_model),
            "_vbsell_cnpj_values",
            side_effect=requests.RequestException("down"),
        ):
            person = self.lead_model._vbsell_company_and_contact(
                self.company, self._contact()
            )
        self.assertTrue(person.parent_id.is_company)
        self.assertEqual(person.parent_id.name, "Chat Name")
        self.assertFalse(person.parent_id.legal_name)
        self.assertEqual(person.name, "Ada Lovelace")

    def test_shareholders_are_attached_without_removing_the_person(self):
        self.company.vbsell_cnpj_search = True
        shareholder = self.env["res.partner"].create({"name": "Shareholder"})
        with patch.object(
            type(self.lead_model),
            "_vbsell_cnpj_values",
            return_value=(
                self._registry(child_ids=[Command.set([shareholder.id])]),
                shareholder,
            ),
        ):
            person = self.lead_model._vbsell_company_and_contact(
                self.company, self._contact()
            )
        company_partner = person.parent_id
        self.assertEqual(shareholder.parent_id, company_partner)
        self.assertIn(person, company_partner.child_ids)
        self.assertEqual(person.name, "Ada Lovelace")

    def test_cpf_does_not_query_the_registry(self):
        self.company.vbsell_cnpj_search = True
        with patch.object(type(self.lead_model), "_vbsell_cnpj_values") as mocked:
            partner = self.lead_model._vbsell_partner(
                self.company,
                self._contact(vat="12345678901"),
            )
        mocked.assert_not_called()
        self.assertFalse(partner.parent_id)

    def test_cnpj_service_call_uses_the_configured_provider(self):
        webservice = self.env["l10n_br_cnpj_search.webservice.abstract"]
        shareholder = self.env["res.partner"].create({"name": "Shareholder"})
        with patch.object(
            type(webservice), "get_api_url", return_value="https://example.test/cnpj"
        ), patch.object(
            type(webservice), "get_headers", return_value={"Accept": "application/json"}
        ), patch.object(
            type(webservice), "validate", return_value={"nome": "Analytical"}
        ), patch.object(
            type(webservice),
            "import_data",
            return_value={
                "legal_name": "Analytical Engines Ltda",
                "child_ids": [Command.set([shareholder.id])],
                "cnpj_cpf": "00000000000191",
            },
        ), patch(
            "odoo.addons.crm_vbsell_cnpj_search.models.crm_lead.requests.get"
        ) as get:
            values, partners = self.lead_model._vbsell_cnpj_values("00000000000191")
        get.assert_called_once_with(
            "https://example.test/cnpj",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        self.assertEqual(values["legal_name"], "Analytical Engines Ltda")
        self.assertNotIn("child_ids", values)
        self.assertNotIn("cnpj_cpf", values)
        self.assertEqual(partners, shareholder)

    def test_missing_provider_url_skips_the_request(self):
        webservice = self.env["l10n_br_cnpj_search.webservice.abstract"]
        with patch.object(type(webservice), "get_api_url", return_value=False), patch(
            "odoo.addons.crm_vbsell_cnpj_search.models.crm_lead.requests.get"
        ) as get:
            values, partners = self.lead_model._vbsell_cnpj_values("00000000000191")
        get.assert_not_called()
        self.assertEqual(values, {})
        self.assertFalse(partners)

    def test_blank_settings_save_keeps_the_lookup_flag(self):
        self.company.vbsell_cnpj_search = True
        self.env["res.config.settings"].create(
            {
                "company_id": self.company.id,
                "vbsell_enabled": False,
                "vbsell_company_uuid": False,
                "vbsell_api_key": False,
                "vbsell_webhook_secret": False,
                "vbsell_user_id": False,
                "vbsell_source_id": False,
                "vbsell_lost_reason_id": False,
                "vbsell_cnpj_search": False,
            }
        )
        self.assertTrue(self.company.vbsell_enabled)
        self.assertTrue(self.company.vbsell_cnpj_search)

    def test_settings_can_disable_the_lookup(self):
        self.company.vbsell_cnpj_search = True
        self.env["res.config.settings"].create(
            {
                "company_id": self.company.id,
                "vbsell_enabled": True,
                "vbsell_company_uuid": "company-uuid",
                "vbsell_cnpj_search": False,
            }
        )
        self.assertFalse(self.company.vbsell_cnpj_search)
        self.assertTrue(self.company.vbsell_enabled)

    def test_settings_form_loads_the_lookup_flag(self):
        self.company.vbsell_cnpj_search = True
        values = self.env["res.config.settings"].default_get(["vbsell_cnpj_search"])
        self.assertTrue(values["vbsell_cnpj_search"])
