This module links Survey participations to CRM opportunities.

It adds a ``lead_id`` field on ``survey.user_input``, so every participation can
point to the opportunity it was collected for, and it lets you mark CRM stages
that can only be reached once the opportunity has at least one **completed**
survey.
