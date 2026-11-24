# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "CRM VBSell CNPJ Search",
    "summary": "Fill VBSell companies from the Brazilian CNPJ service",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/crm-addons",
    "maintainers": ["marcelsavegnago"],
    "development_status": "Beta",
    "category": "Sales/CRM",
    "depends": ["crm_vbsell", "l10n_br_cnpj_search"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
