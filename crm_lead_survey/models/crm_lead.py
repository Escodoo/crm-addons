# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    survey_user_input_ids = fields.One2many(
        comodel_name="survey.user_input",
        inverse_name="lead_id",
        string="Surveys",
    )
    survey_count = fields.Integer(
        string="# Surveys",
        compute="_compute_survey_count",
    )
    survey_done_count = fields.Integer(
        string="# Completed Surveys",
        compute="_compute_survey_count",
    )

    @api.depends("survey_user_input_ids", "survey_user_input_ids.state")
    def _compute_survey_count(self):
        groups = (
            self.env["survey.user_input"]
            .sudo()
            .read_group(
                [("lead_id", "in", self.ids)],
                ["lead_id", "state"],
                ["lead_id", "state"],
                lazy=False,
            )
        )
        totals = {}
        done_totals = {}
        for group in groups:
            lead_id = group["lead_id"][0]
            count = group["__count"]
            totals[lead_id] = totals.get(lead_id, 0) + count
            if group["state"] == "done":
                done_totals[lead_id] = done_totals.get(lead_id, 0) + count
        for lead in self:
            lead_id = lead._origin.id
            lead.survey_count = totals.get(lead_id, 0)
            lead.survey_done_count = done_totals.get(lead_id, 0)

    @api.constrains("stage_id", "survey_user_input_ids")
    def _check_stage_survey_required(self):
        for lead in self:
            if not lead.stage_id.survey_required:
                continue
            if not lead.sudo().survey_user_input_ids.filtered(
                lambda user_input: user_input.state == "done"
            ):
                raise ValidationError(
                    _("This stage requires at least one completed survey.")
                )

    def action_view_surveys(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "survey.action_survey_user_input"
        )
        action["domain"] = [("lead_id", "=", self.id)]
        action["context"] = {
            "default_lead_id": self.id,
            "search_default_group_by_survey": True,
        }
        return action

    def action_open_survey_wizard(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "crm_lead_survey.crm_lead_survey_wizard_action"
        )
        action["context"] = {
            "default_lead_id": self.id,
            "default_partner_id": self.partner_id.id,
        }
        return action
