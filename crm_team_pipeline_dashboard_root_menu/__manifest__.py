# Copyright 2020 Escodoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'CRM Team Pipeline Dashboard Default Root Menu',
    'summary': """
        This module changes the CRM root menu to open Team Pipeline Dashboard""",
    'version': '12.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Escodoo,Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/crm',
    'depends': [
        'crm',
    ],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'demo': [
    ],
}
