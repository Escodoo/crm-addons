# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCrmLeadSurvey(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Partner", "email": "partner@example.org"}
        )
        cls.survey = cls.env["survey.survey"].create(
            {
                "title": "Satisfaction",
                "question_and_page_ids": [
                    (0, 0, {"title": "How was it?", "question_type": "char_box"})
                ],
            }
        )
        cls.stage_new = cls.env["crm.stage"].create(
            {"name": "Test New", "sequence": 100}
        )
        cls.stage_required = cls.env["crm.stage"].create(
            {"name": "Test Qualified", "sequence": 101, "survey_required": True}
        )
        cls.lead = cls.env["crm.lead"].create(
            {
                "name": "Test Opportunity",
                "type": "opportunity",
                "partner_id": cls.partner.id,
                "stage_id": cls.stage_new.id,
            }
        )

    def _start_survey(self, lead=None, start_now=False):
        """Run the wizard the same way the form button does."""
        lead = lead or self.lead
        action = lead.action_open_survey_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .create({"survey_id": self.survey.id, "start_now": start_now})
        )
        wizard.action_confirm()
        return lead.survey_user_input_ids[-1]

    def test_wizard_defaults_from_lead(self):
        action = self.lead.action_open_survey_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .create({"survey_id": self.survey.id})
        )
        self.assertEqual(wizard.lead_id, self.lead)
        self.assertEqual(wizard.partner_id, self.partner)

    def test_wizard_creates_linked_answer(self):
        user_input = self._start_survey()
        self.assertEqual(user_input.lead_id, self.lead)
        self.assertEqual(user_input.survey_id, self.survey)
        self.assertEqual(user_input.partner_id, self.partner)
        self.assertEqual(user_input.state, "new")
        self.assertEqual(self.lead.survey_count, 1)
        self.assertEqual(self.lead.survey_done_count, 0)

    def test_wizard_start_now_returns_survey_url(self):
        action = self.lead.action_open_survey_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .create({"survey_id": self.survey.id, "start_now": True})
        )
        result = wizard.action_confirm()
        user_input = self.lead.survey_user_input_ids
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertIn(user_input.access_token, result["url"])
        self.assertEqual(result["target"], "self")

    def test_action_view_surveys_only_shows_own_answers(self):
        user_input = self._start_survey()
        other_lead = self.env["crm.lead"].create(
            {"name": "Other Opportunity", "type": "opportunity"}
        )
        self._start_survey(lead=other_lead)
        action = self.lead.action_view_surveys()
        found = self.env["survey.user_input"].search(action["domain"])
        self.assertEqual(found, user_input)
        self.assertEqual(action["context"]["default_lead_id"], self.lead.id)

    def test_stage_without_survey_is_not_restricted(self):
        self.lead.stage_id = self.stage_new
        self.assertEqual(self.lead.stage_id, self.stage_new)

    def test_stage_required_blocked_without_survey(self):
        with self.assertRaises(ValidationError):
            self.lead.write({"stage_id": self.stage_required.id})

    def test_stage_required_blocked_with_survey_in_progress(self):
        user_input = self._start_survey()
        user_input.state = "in_progress"
        with self.assertRaises(ValidationError):
            self.lead.write({"stage_id": self.stage_required.id})

    def test_stage_required_allowed_with_survey_done(self):
        user_input = self._start_survey()
        user_input.state = "done"
        self.lead.write({"stage_id": self.stage_required.id})
        self.assertEqual(self.lead.stage_id, self.stage_required)
        self.assertEqual(self.lead.survey_done_count, 1)

    def test_stage_required_blocked_on_multi_write(self):
        """Dragging several opportunities at once is checked record by record."""
        user_input = self._start_survey()
        user_input.state = "done"
        other_lead = self.env["crm.lead"].create(
            {"name": "Other Opportunity", "type": "opportunity"}
        )
        with self.assertRaises(ValidationError):
            (self.lead | other_lead).write({"stage_id": self.stage_required.id})

    def test_stage_required_checked_on_lead_creation(self):
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].create(
                {
                    "name": "Born Qualified",
                    "type": "opportunity",
                    "stage_id": self.stage_required.id,
                }
            )
