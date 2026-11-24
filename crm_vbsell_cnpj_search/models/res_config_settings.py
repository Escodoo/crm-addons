# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vbsell_cnpj_search = fields.Boolean(
        related="company_id.vbsell_cnpj_search",
        readonly=False,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res["vbsell_cnpj_search"] = self.env.company.vbsell_cnpj_search
        return res

    @api.model
    def _vbsell_keep_stored_settings(self, vals):
        """Keep the CNPJ lookup flag when a blank VBSell form is saved.

        The base module drops the other VBSell fields in that case. This flag
        is not one of them, so a form that was never loaded would turn the
        lookup off.
        """
        blank = self._vbsell_payload_is_blank(vals)
        super()._vbsell_keep_stored_settings(vals)
        if not blank:
            return
        company = self._vbsell_settings_company(vals)
        if (
            company
            and company.vbsell_cnpj_search
            and not vals.get("vbsell_cnpj_search")
        ):
            vals.pop("vbsell_cnpj_search", None)
