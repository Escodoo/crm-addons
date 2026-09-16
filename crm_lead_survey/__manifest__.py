# Copyright 2026 - TODAY, Wesley Oliveira <wesley.oliveira@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "CRM Lead Survey",
    "summary": """
        Link surveys to CRM opportunities and require them per stage""",
    "version": "16.0.1.0.0",
    "category": "Customer Relationship Management",
    "license": "AGPL-3",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/crm-addons",
    "depends": ["crm", "survey"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/crm_lead_survey_wizard_views.xml",
        "views/crm_lead_views.xml",
        "views/crm_stage_views.xml",
        "views/survey_user_input_views.xml",
    ],
}
