# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    """Copy the legacy Studio column into the module field when it exists."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'crm_lead'
           AND column_name = 'x_vbsell_id'
        """
    )
    if not env.cr.fetchone():
        return
    env.cr.execute(
        """
        UPDATE crm_lead
           SET vbsell_opportunity_id = x_vbsell_id::varchar
         WHERE COALESCE(vbsell_opportunity_id, '') = ''
           AND x_vbsell_id IS NOT NULL
           AND x_vbsell_id::varchar <> ''
        """
    )
