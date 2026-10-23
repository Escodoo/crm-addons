# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import Form, TransactionCase


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
        cls.survey_other = cls.env["survey.survey"].create(
            {
                "title": "Qualification",
                "question_and_page_ids": [
                    (0, 0, {"title": "Budget?", "question_type": "char_box"})
                ],
            }
        )
        cls.stage_new = cls.env["crm.stage"].create(
            {"name": "Test New", "sequence": 100}
        )
        cls.stage_required = cls.env["crm.stage"].create(
            {"name": "Test Qualified", "sequence": 101, "survey_required": True}
        )
        cls.stage_specific = cls.env["crm.stage"].create(
            {
                "name": "Test Proposition",
                "sequence": 102,
                "survey_required": True,
                "survey_id": cls.survey_other.id,
            }
        )
        cls.stage_after = cls.env["crm.stage"].create(
            {"name": "Test Negotiation", "sequence": 103}
        )
        cls.lead = cls.env["crm.lead"].create(
            {
                "name": "Test Opportunity",
                "type": "opportunity",
                "partner_id": cls.partner.id,
                "stage_id": cls.stage_new.id,
            }
        )

    def _create_lead(self, stage, name="Other Opportunity"):
        return self.env["crm.lead"].create(
            {"name": name, "type": "opportunity", "stage_id": stage.id}
        )

    def _add_answer(self, lead, survey, state):
        """Create a participation directly, bypassing the wizard checks."""
        answer = survey._create_answer(user=self.env.user, lead_id=lead.id)
        answer.state = state
        return answer

    def _start_survey(self, lead=None, start_now=False, survey=None):
        """Run the wizard the same way the form button does."""
        lead = lead or self.lead
        survey = survey or self.survey
        action = lead.action_open_survey_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .create({"survey_id": survey.id, "start_now": start_now})
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

    def test_leave_stage_without_requirement(self):
        """Leaving a stage that requires nothing is free, whatever comes next."""
        self.lead.write({"stage_id": self.stage_required.id})
        self.assertEqual(self.lead.stage_id, self.stage_required)

    def test_leave_required_stage_blocked_without_survey(self):
        lead = self._create_lead(self.stage_required)
        with self.assertRaisesRegex(ValidationError, "Test Qualified"):
            lead.write({"stage_id": self.stage_specific.id})

    def test_leave_required_stage_blocked_with_survey_in_progress(self):
        lead = self._create_lead(self.stage_required)
        self._start_survey(lead=lead).state = "in_progress"
        with self.assertRaises(ValidationError):
            lead.write({"stage_id": self.stage_specific.id})

    def test_leave_required_stage_allowed_with_survey_done(self):
        lead = self._create_lead(self.stage_required)
        self._start_survey(lead=lead).state = "done"
        lead.write({"stage_id": self.stage_specific.id})
        self.assertEqual(lead.stage_id, self.stage_specific)
        self.assertEqual(lead.survey_done_count, 1)

    def test_leave_required_stage_blocked_when_skipping_stages(self):
        lead = self._create_lead(self.stage_required)
        with self.assertRaises(ValidationError):
            lead.write({"stage_id": self.stage_after.id})

    def test_leave_required_stage_blocked_on_multi_write(self):
        """Dragging several opportunities at once is checked record by record."""
        lead = self._create_lead(self.stage_required)
        self._start_survey(lead=lead).state = "done"
        other_lead = self._create_lead(self.stage_required, name="Not answered")
        with self.assertRaises(ValidationError):
            (lead | other_lead).write({"stage_id": self.stage_specific.id})

    def test_move_back_from_required_stage_allowed(self):
        """The survey only gates moving forward; going back is always allowed."""
        lead = self._create_lead(self.stage_specific)
        lead.write({"stage_id": self.stage_new.id})
        self.assertEqual(lead.stage_id, self.stage_new)

    def test_create_lead_in_required_stage_allowed(self):
        lead = self._create_lead(self.stage_specific, name="Born Proposition")
        self.assertEqual(lead.stage_id, self.stage_specific)

    def test_stage_specific_survey_blocked_with_other_survey_done(self):
        """A completed survey other than the one set on the stage is not enough."""
        lead = self._create_lead(self.stage_specific)
        self._add_answer(lead, self.survey, "done")
        with self.assertRaisesRegex(ValidationError, "Qualification"):
            lead.write({"stage_id": self.stage_after.id})

    def test_stage_specific_survey_blocked_while_in_progress(self):
        lead = self._create_lead(self.stage_specific)
        self._add_answer(lead, self.survey_other, "in_progress")
        with self.assertRaises(ValidationError):
            lead.write({"stage_id": self.stage_after.id})

    def test_stage_specific_survey_allowed_when_done(self):
        lead = self._create_lead(self.stage_specific)
        self._add_answer(lead, self.survey, "in_progress")
        self._add_answer(lead, self.survey_other, "done")
        lead.write({"stage_id": self.stage_after.id})
        self.assertEqual(lead.stage_id, self.stage_after)

    def test_stage_specific_survey_done_on_other_lead_does_not_count(self):
        lead = self._create_lead(self.stage_specific)
        self._start_survey(survey=self.survey_other).state = "done"
        with self.assertRaises(ValidationError):
            lead.write({"stage_id": self.stage_after.id})

    def test_stage_survey_ignored_when_not_required(self):
        self.stage_specific.survey_required = False
        lead = self._create_lead(self.stage_specific)
        lead.write({"stage_id": self.stage_after.id})
        self.assertEqual(lead.stage_id, self.stage_after)

    def test_stage_survey_cleared_when_unchecking_required(self):
        with Form(self.stage_specific) as stage_form:
            stage_form.survey_required = False
        self.assertFalse(self.stage_specific.survey_id)

    def test_wizard_locks_current_stage_survey(self):
        lead = self._create_lead(self.stage_specific)
        action = lead.action_open_survey_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .create({"start_now": False})
        )
        self.assertEqual(wizard.stage_id, self.stage_specific)
        self.assertTrue(wizard.survey_locked)
        self.assertEqual(wizard.survey_id, self.survey_other)
        wizard.action_confirm()
        self.assertEqual(lead.survey_user_input_ids.survey_id, self.survey_other)

    def test_wizard_ignores_next_stage_survey(self):
        """The survey of a later stage cannot be forced from an earlier one."""
        self.stage_required.survey_id = self.survey_other
        action = self.lead.action_open_survey_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .create({"survey_id": self.survey.id})
        )
        self.assertEqual(wizard.stage_id, self.stage_new)
        self.assertFalse(wizard.survey_locked)

    def test_wizard_rejects_other_survey_when_locked(self):
        lead = self._create_lead(self.stage_specific)
        with self.assertRaisesRegex(ValidationError, "Qualification"):
            self._start_survey(lead=lead, survey=self.survey)

    def test_wizard_free_choice_when_stage_accepts_any_survey(self):
        lead = self._create_lead(self.stage_required)
        user_input = self._start_survey(lead=lead, survey=self.survey_other)
        self.assertEqual(user_input.survey_id, self.survey_other)

    def test_lead_back_url_for_internal_user(self):
        user_input = self._start_survey()
        url = user_input.get_lead_back_url()
        self.assertIn("id=%s&model=crm.lead" % self.lead.id, url)

    def test_lead_back_url_hidden_without_lead_or_for_public(self):
        user_input = self._start_survey()
        public_user = self.env.ref("base.public_user")
        self.assertFalse(user_input.with_user(public_user).sudo().get_lead_back_url())
        user_input.lead_id = False
        self.assertFalse(user_input.get_lead_back_url())

    def test_done_page_shows_back_to_lead_button(self):
        user_input = self._start_survey()
        html = self.env["ir.qweb"]._render(
            "survey.survey_fill_form_done",
            {"survey": user_input.survey_id, "answer": user_input},
        )
        self.assertIn(user_input.get_lead_back_url(), str(html).replace("&amp;", "&"))
