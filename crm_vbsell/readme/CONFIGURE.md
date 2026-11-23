Open CRM settings and, for each company:

- Enable the sync and set the API base URL, API key and webhook secret.
- Set the VBSell company UUID so inbound events find this company.
- Choose the default salesperson, source and lost reason.
- Choose the minimum VBSell stage that may create a lead. Earlier stages update an
  existing lead and do not create one.

On each CRM stage, set VBSell Stage. Use at most one stage per value on a sales team.
Stages left empty are not pushed to VBSell. The Won value can only be set on a stage
that is marked as won. Lost is not a stage.

Outbound updates use the `root.vbsell` job channel. Give that channel a capacity in the
queue job configuration, for example `channels = root:2,root.vbsell:1`. A failed call is
retried. The lead chatter receives the error when the last retry fails.
