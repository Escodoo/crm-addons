# Copyright 2023 - TODAY, Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "CRM SLA",
    "summary": """
        CRM SLA""",
    "version": "12.0.1.0.0",
    "license": "AGPL-3",
    "author": "Escodoo",
    "website": "https://github.com/escodoo/crm-addons",
    "depends": ["crm", "sale_crm", "resource"],
    "data": [
        "views/crm_lead.xml",
        "views/crm_sla.xml",
        "views/crm_sla_line.xml",
        "views/crm_team.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
    ],
    "demo": [],
}
