# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "CRM VBSell",
    "summary": "Sync CRM opportunities with VBSell",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/crm-addons",
    "maintainers": ["marcelsavegnago"],
    "development_status": "Beta",
    "category": "Sales/CRM",
    "depends": ["crm", "utm", "queue_job"],
    "data": [
        "data/queue_job_data.xml",
        "views/crm_stage_views.xml",
        "views/crm_lead_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
