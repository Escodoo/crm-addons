# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

# A Settings save always creates a new record and sends every field in the
# form. These identify a VBSell block that was never loaded (all empty), as
# opposed to an intentional edit that still carries the company UUID.
_VBSELL_BLANK_MARKERS = (
    "vbsell_enabled",
    "vbsell_company_uuid",
    "vbsell_api_key",
    "vbsell_webhook_secret",
    "vbsell_user_id",
    "vbsell_source_id",
    "vbsell_lost_reason_id",
)
_VBSELL_FIELDS = _VBSELL_BLANK_MARKERS + (
    "vbsell_api_base_url",
    "vbsell_min_create_stage",
)
_VBSELL_SECRETS = ("vbsell_api_key", "vbsell_webhook_secret")


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

    @api.model
    def get_values(self):
        """Load the company VBSell values into the settings form.

        Related fields are not part of ``default_get``. A form opened without
        them shows the block disabled, and the next Save writes that empty
        state back onto the company.
        """
        res = super().get_values()
        company = self.env.company
        res.update(
            {
                "vbsell_enabled": company.vbsell_enabled,
                "vbsell_api_base_url": company.vbsell_api_base_url,
                "vbsell_company_uuid": company.vbsell_company_uuid,
                "vbsell_user_id": company.vbsell_user_id.id,
                "vbsell_source_id": company.vbsell_source_id.id,
                "vbsell_lost_reason_id": company.vbsell_lost_reason_id.id,
                "vbsell_min_create_stage": company.vbsell_min_create_stage,
            }
        )
        if self.env.user.has_group("base.group_system"):
            secured = company.sudo()
            res["vbsell_api_key"] = secured.vbsell_api_key
            res["vbsell_webhook_secret"] = secured.vbsell_webhook_secret
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._vbsell_keep_stored_settings(vals)
        return super().create(vals_list)

    @api.model
    def _vbsell_keep_stored_settings(self, vals):
        """Drop a settings payload that would erase a stored VBSell setup.

        Settings always sends every field. A form that still has the empty
        defaults (opened before the setup, or saved by someone else) would
        write those defaults onto the company and turn the sync off.
        """
        company = self._vbsell_settings_company(vals)
        if not company or not self._vbsell_company_is_configured(company):
            return
        if self._vbsell_payload_is_blank(vals):
            for name in _VBSELL_FIELDS:
                vals.pop(name, None)
            return
        for secret in _VBSELL_SECRETS:
            if secret in vals and not vals[secret] and company[secret]:
                vals.pop(secret, None)

    @api.model
    def _vbsell_settings_company(self, vals):
        company_id = vals.get("company_id") or self.env.company.id
        return self.env["res.company"].browse(company_id).sudo().exists()

    @api.model
    def _vbsell_company_is_configured(self, company):
        return bool(
            company.vbsell_enabled
            or company.vbsell_company_uuid
            or company.vbsell_api_key
            or company.vbsell_webhook_secret
            or company.vbsell_user_id
            or company.vbsell_source_id
            or company.vbsell_lost_reason_id
        )

    @api.model
    def _vbsell_payload_is_blank(self, vals):
        if any(name not in vals for name in _VBSELL_BLANK_MARKERS):
            return False
        return not any(vals[name] for name in _VBSELL_BLANK_MARKERS)
