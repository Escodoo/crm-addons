Synchronize Odoo CRM opportunities with VBSell.

Inbound stage changes arrive on a signed webhook. Outbound stage, won and lost changes
are sent back to the VBSell API by a retried job. Writes that came from VBSell are not
pushed again.
