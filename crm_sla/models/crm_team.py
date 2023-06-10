# Copyright 2023 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, api


class CrmTeam(models.Model):
    _inherit = "crm.team"

    use_sla = fields.Boolean(string="Use SLA")
    resource_calendar_id = fields.Many2one(
        "resource.calendar",
        "Working Hours",
        default=lambda self: self.env.user.company_id.resource_calendar_id,
    )

    start_date_sla = fields.Datetime(
        string="Start Date SLA")

    @api.onchange('use_sla')
    def _onchange_use_sla(self):
        if self.use_sla:
            self.start_date_sla = fields.Datetime.now()
        else:
            self.start_date_sla = False
