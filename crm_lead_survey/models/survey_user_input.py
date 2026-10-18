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

    def get_lead_back_url(self):
        """URL of the opportunity form in the backend, offered at the end of
        the survey to go back to it. Only internal users get it, since the
        contact answering through the survey link has no access to the CRM."""
        self.ensure_one()
        if not self.lead_id or not self.env.user._is_internal():
            return False
        action = self.env.ref("crm.crm_lead_action_pipeline")
        return "/web#id=%s&model=crm.lead&view_type=form&action=%s" % (
            self.lead_id.id,
            action.id,
        )
