# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CrmLeadSurveyWizard(models.TransientModel):
    _name = "crm.lead.survey.wizard"
    _description = "Start a survey from an opportunity"

    lead_id = fields.Many2one(
        comodel_name="crm.lead",
        string="Opportunity",
        required=True,
        ondelete="cascade",
    )
    survey_id = fields.Many2one(
        comodel_name="survey.survey",
        string="Survey",
        required=True,
        domain=[("active", "=", True)],
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        help="Contact the participation is created for. Ignored when the "
        "survey is answered now, since it then belongs to the current user.",
    )
    deadline = fields.Datetime(
        string="Answer Deadline",
        help="Date until which the contact can open the survey and submit answers.",
    )
    start_now = fields.Boolean(
        string="Answer now",
        default=True,
        help="Open the survey right away and answer it as the current user. "
        "Uncheck it to only register the participation for the contact, for "
        "instance to send them the link later.",
    )

    @api.onchange("lead_id")
    def _onchange_lead_id(self):
        for wizard in self:
            wizard.partner_id = wizard.lead_id.partner_id

    def _prepare_answer_values(self):
        self.ensure_one()
        values = {"lead_id": self.lead_id.id}
        if self.deadline:
            values["deadline"] = self.deadline
        return values

    def _create_survey_answer(self):
        self.ensure_one()
        survey = self.survey_id.sudo()
        values = self._prepare_answer_values()
        if self.start_now:
            return survey._create_answer(user=self.env.user, **values)
        return survey._create_answer(
            partner=self.partner_id or False,
            email=self.partner_id.email or self.lead_id.email_from or False,
            **values,
        )

    def action_confirm(self):
        self.ensure_one()
        answer = self._create_survey_answer()
        if not self.start_now:
            return {"type": "ir.actions.act_window_close"}
        return self.survey_id.action_start_survey(answer=answer)
