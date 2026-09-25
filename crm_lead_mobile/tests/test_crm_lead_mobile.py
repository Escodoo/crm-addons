# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import Form, TransactionCase


class TestCrmLeadMobile(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Mobile Partner", "mobile": "+55 11 99999-0001"}
        )
        cls.partner_other = cls.env["res.partner"].create(
            {"name": "Other Partner", "mobile": "+55 11 99999-0002"}
        )
        cls.partner_no_mobile = cls.env["res.partner"].create(
            {"name": "No Mobile Partner", "phone": "+55 11 3333-0000"}
        )

    def _create_opportunity(self, **vals):
        lead = self.env["crm.lead"].create(
            dict({"name": "Opportunity", "type": "opportunity"}, **vals)
        )
        # Store the computed mobile now, as the end of a web request would
        lead.flush_recordset()
        return lead

    def test_create_fills_mobile_from_partner(self):
        lead = self._create_opportunity(partner_id=self.partner.id)
        self.assertEqual(lead.mobile, self.partner.mobile)

    def test_create_partner_without_mobile(self):
        lead = self._create_opportunity(partner_id=self.partner_no_mobile.id)
        self.assertFalse(lead.mobile)

    def test_create_explicit_mobile_is_kept(self):
        lead = self._create_opportunity(
            partner_id=self.partner.id, mobile="+55 21 98888-7777"
        )
        self.assertEqual(lead.mobile, "+55 21 98888-7777")

    def test_write_partner_updates_mobile(self):
        lead = self._create_opportunity(partner_id=self.partner.id)
        lead.write({"partner_id": self.partner_other.id})
        self.assertEqual(lead.mobile, self.partner_other.mobile)

    def test_write_partner_without_mobile_keeps_mobile(self):
        lead = self._create_opportunity(partner_id=self.partner.id)
        lead.write({"partner_id": self.partner_no_mobile.id})
        self.assertEqual(lead.mobile, "+55 11 99999-0001")

    def test_convert_lead_to_partner_without_mobile_keeps_mobile(self):
        lead = self.env["crm.lead"].create(
            {"name": "Lead", "type": "lead", "mobile": "+55 21 98888-7777"}
        )
        lead.flush_recordset()
        wizard = (
            self.env["crm.lead2opportunity.partner"]
            .with_context(
                active_model="crm.lead", active_id=lead.id, active_ids=lead.ids
            )
            .create(
                {
                    "name": "convert",
                    "action": "exist",
                    "partner_id": self.partner_no_mobile.id,
                }
            )
        )
        wizard.action_apply()
        self.assertEqual(lead.type, "opportunity")
        self.assertEqual(lead.mobile, "+55 21 98888-7777")

    def test_remove_partner_keeps_mobile(self):
        lead = self._create_opportunity(partner_id=self.partner.id)
        lead.write({"partner_id": False})
        self.assertEqual(lead.mobile, "+55 11 99999-0001")

    def test_edit_mobile_does_not_change_partner(self):
        lead = self._create_opportunity(partner_id=self.partner.id)
        lead.write({"mobile": "+55 21 98888-7777"})
        self.assertEqual(lead.mobile, "+55 21 98888-7777")
        self.assertEqual(self.partner.mobile, "+55 11 99999-0001")

    def test_partner_mobile_change_does_not_change_lead(self):
        lead = self._create_opportunity(partner_id=self.partner.id)
        self.partner.mobile = "+55 11 90000-0000"
        self.assertEqual(lead.mobile, "+55 11 99999-0001")

    def test_form_onchange_partner(self):
        form = Form(
            self.env["crm.lead"].with_context(default_type="opportunity"),
            view="crm.crm_lead_view_form",
        )
        form.name = "Opportunity"
        form.partner_id = self.partner
        self.assertEqual(form.mobile, self.partner.mobile)
        form.partner_id = self.partner_no_mobile
        self.assertEqual(form.mobile, self.partner.mobile)
        form.partner_id = self.partner_other
        form.mobile = "+55 21 98888-7777"
        lead = form.save()
        self.assertEqual(lead.mobile, "+55 21 98888-7777")
        self.assertEqual(self.partner_other.mobile, "+55 11 99999-0002")

    def test_quick_create_form_onchange_partner(self):
        form = Form(
            self.env["crm.lead"].with_context(default_type="opportunity"),
            view="crm.quick_create_opportunity_form",
        )
        form.name = "Quick Opportunity"
        form.partner_id = self.partner
        self.assertEqual(form.mobile, self.partner.mobile)
        lead = form.save()
        self.assertEqual(lead.mobile, self.partner.mobile)

    def test_views_show_mobile(self):
        for xmlid in ("crm.crm_lead_view_form", "crm.quick_create_opportunity_form"):
            arch = self.env["crm.lead"].get_view(self.env.ref(xmlid).id)["arch"]
            self.assertIn('name="mobile"', arch, xmlid)
