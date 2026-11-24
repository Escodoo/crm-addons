When the option is on, a VBSell contact with a CNPJ still creates the company
and the linked person. Odoo then asks the configured CNPJ service for the
official name, address and fiscal data and writes them on the company. The
opportunity customer remains the person.

A company that already has a legal name is not queried again. Shareholders
returned by SERPRO are attached under the company and do not replace the
VBSell person. If the service times out or rejects the CNPJ, the opportunity
is created with the data VBSell sent.
