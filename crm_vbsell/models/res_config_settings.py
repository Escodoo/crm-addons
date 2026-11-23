# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vbsell_enabled = fields.Boolean(
        related="company_id.vbsell_enabled",
        readonly=False,
    )
    vbsell_api_base_url = fields.Char(
        related="company_id.vbsell_api_base_url",
        readonly=False,
    )
    vbsell_api_key = fields.Char(
        related="company_id.vbsell_api_key",
        readonly=False,
        groups="base.group_system",
    )
    vbsell_webhook_secret = fields.Char(
        related="company_id.vbsell_webhook_secret",
        readonly=False,
        groups="base.group_system",
    )
    vbsell_company_uuid = fields.Char(
        related="company_id.vbsell_company_uuid",
        readonly=False,
    )
    vbsell_user_id = fields.Many2one(
        related="company_id.vbsell_user_id",
        readonly=False,
    )
    vbsell_source_id = fields.Many2one(
        related="company_id.vbsell_source_id",
        readonly=False,
    )
    vbsell_lost_reason_id = fields.Many2one(
        related="company_id.vbsell_lost_reason_id",
        readonly=False,
    )
    vbsell_min_create_stage = fields.Selection(
        related="company_id.vbsell_min_create_stage",
        readonly=False,
    )
