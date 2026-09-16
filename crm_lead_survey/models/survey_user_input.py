# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    lead_id = fields.Many2one(
        comodel_name="crm.lead",
        string="Opportunity",
        ondelete="set null",
        index=True,
        help="Opportunity this participation is linked to.",
    )
