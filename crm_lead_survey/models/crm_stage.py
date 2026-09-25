# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CrmStage(models.Model):
    _inherit = "crm.stage"

    survey_required = fields.Boolean(
        string="Survey required",
        help="If checked, an opportunity can only be moved to this stage when "
        "it has at least one completed survey linked to it.",
    )
    survey_id = fields.Many2one(
        comodel_name="survey.survey",
        string="Required survey",
        ondelete="restrict",
        help="Survey that must be completed for the opportunity before it can "
        "be moved to this stage. If empty, any completed survey is accepted.",
    )

    @api.onchange("survey_required")
    def _onchange_survey_required(self):
        for stage in self.filtered(lambda stage: not stage.survey_required):
            stage.survey_id = False
