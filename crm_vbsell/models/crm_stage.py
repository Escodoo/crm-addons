# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..const import VBSELL_OPEN_STAGES


class CrmStage(models.Model):
    _inherit = "crm.stage"

    vbsell_stage = fields.Selection(
        selection=VBSELL_OPEN_STAGES,
        string="VBSell Stage",
    )

    @api.constrains("vbsell_stage", "team_id", "is_won")
    def _check_vbsell_stage(self):
        for stage in self.filtered("vbsell_stage"):
            duplicate = self.search(
                [
                    ("id", "!=", stage.id),
                    ("vbsell_stage", "=", stage.vbsell_stage),
                    ("team_id", "=", stage.team_id.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "Only one stage per sales team can use the VBSell "
                        "stage %(stage)s.",
                        stage=stage.vbsell_stage,
                    )
                )
            if stage.vbsell_stage == "won" and not stage.is_won:
                raise ValidationError(
                    _(
                        "The VBSell Won value can only be set on a stage "
                        "marked as won."
                    )
                )
