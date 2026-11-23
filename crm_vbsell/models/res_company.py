# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..const import VBSELL_OPEN_STAGES


class ResCompany(models.Model):
    _inherit = "res.company"

    vbsell_enabled = fields.Boolean(string="VBSell Sync Enabled")
    vbsell_api_base_url = fields.Char(
        string="VBSell API Base URL",
        default="https://vbsell.com",
    )
    vbsell_api_key = fields.Char(
        string="VBSell API Key",
        groups="base.group_system",
    )
    vbsell_webhook_secret = fields.Char(
        string="VBSell Webhook Secret",
        groups="base.group_system",
    )
    vbsell_company_uuid = fields.Char(
        string="VBSell Company UUID",
        index=True,
    )
    vbsell_user_id = fields.Many2one(
        comodel_name="res.users",
        string="VBSell Default Salesperson",
    )
    vbsell_source_id = fields.Many2one(
        comodel_name="utm.source",
        string="VBSell Default Source",
    )
    vbsell_lost_reason_id = fields.Many2one(
        comodel_name="crm.lost.reason",
        string="VBSell Default Lost Reason",
    )
    vbsell_min_create_stage = fields.Selection(
        selection=VBSELL_OPEN_STAGES,
        string="VBSell Minimum Stage to Create",
        default="qualified",
        required=True,
    )

    @api.constrains("vbsell_company_uuid")
    def _check_vbsell_company_uuid(self):
        for company in self.filtered("vbsell_company_uuid"):
            duplicate = self.search(
                [
                    ("id", "!=", company.id),
                    ("vbsell_company_uuid", "=", company.vbsell_company_uuid),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("This VBSell company UUID is already used by another company.")
                )
