# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    vbsell_cnpj_search = fields.Boolean(
        string="Look Up VBSell CNPJ",
        help=(
            "When a VBSell contact has a CNPJ, fill the company from the "
            "Brazilian CNPJ service configured in the localization settings. "
            "A company that already has a legal name is not queried again."
        ),
    )
