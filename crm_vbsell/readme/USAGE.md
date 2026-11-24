Point the VBSell webhook to `https://<odoo>/vbsell/webhook/opportunity` and subscribe it
to `opportunity.stage_changed` only. The same secret configured in Odoo must sign the
request.

A VBSell stage at or above the configured minimum creates the partner and the
opportunity. When the contact tax id is a CNPJ, Odoo creates the company and a
contact linked to that company. The opportunity customer is the contact. A CPF
or any other tax id stays a single partner. Later stage changes, including won and lost, update that opportunity.
Changing the stage in Odoo enqueues one job per lead. When the job runs, it sends the
stage that is current at that moment, including won and lost. A stage without a VBSell
value is not sent.
