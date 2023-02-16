# Copyright 2023 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from odoo.addons.crm.models.crm_stage import AVAILABLE_PRIORITIES


class CrmSla(models.Model):
    _name = "crm.sla"
    _description = "SLA"

    name = fields.Char(string="Name", required=True)
    description = fields.Html("SLA Policy Description", translate=True)
    active = fields.Boolean("Active", default=True)
    duration = fields.Integer(string="Duration (hours)", required=True)
    team_id = fields.Many2one("crm.team", "Team", required=True)
    target_stage_id = fields.Many2one(
        comodel_name="crm.stage", string="Target Stage", required=True
    )
    partner_ids = fields.Many2many(comodel_name="res.partner", string="Partners")
    tag_ids = fields.Many2many(comodel_name="crm.lead.tag", string="Tags")
    priority = fields.Selection(
        AVAILABLE_PRIORITIES,
        string="Priority",
        index=True,
        default=AVAILABLE_PRIORITIES[0][0],
    )
    sla_line_ids = fields.One2many(
        "crm.sla.line", "sla_id", string="SLA Lines", copy=True
    )
    lead_ids = fields.One2many("crm.lead", string="Leads", compute="_compute_lead_ids")

    @api.depends("sla_line_ids", "sla_line_ids.lead_id")
    def _compute_lead_ids(self):
        for sla in self:
            sla.lead_ids = sla.sla_line_ids.mapped("lead_id")

    _sql_constraints = [
        (
            "duration_positive",
            "CHECK(duration >= 0)",
            "The duration of an SLA must be positive.",
        ),
    ]
