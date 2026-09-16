# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CrmStage(models.Model):
    _inherit = "crm.stage"

    survey_required = fields.Boolean(
        string="Survey required",
        help="If checked, an opportunity can only be moved to this stage when "
        "it has at least one completed survey linked to it.",
    )
