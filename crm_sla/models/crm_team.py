# Copyright 2023 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = "crm.team"

    use_sla = fields.Boolean(string="Use SLA")
    calendar_id = fields.Many2one(
        "resource.calendar",
        "Working Hours",
        default=lambda self: self.env["res.company"]
        ._company_default_get()
        .resource_calendar_id,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
