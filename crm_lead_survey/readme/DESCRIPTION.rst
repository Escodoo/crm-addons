This module links Survey participations to CRM opportunities.

It adds a ``lead_id`` field on ``survey.user_input``, so every participation can
point to the opportunity it was collected for, and it lets you mark CRM stages
that the opportunity can only leave (moving forward) once it has a **completed** survey -
either any survey, or a specific survey chosen on the stage.
