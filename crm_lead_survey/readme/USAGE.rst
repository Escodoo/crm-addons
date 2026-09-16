On an opportunity form:

* **Start Survey** opens a wizard where you pick the survey template and the
  contact. Confirming it creates the ``survey.user_input`` already linked to the
  opportunity and (optionally) opens the survey so it can be answered right
  away.
* The **Surveys** smart button shows only the participations of that
  opportunity.

To require a survey on a stage, go to *CRM > Configuration > Stages*, open the
stage and check **Survey required**. From then on, moving an opportunity to
that stage - from the form or by dragging it in the kanban - raises an error
unless at least one linked participation is in the *Completed* state. A survey
that was only started or is still in progress does not unlock the stage.

Participations can also be searched and grouped by opportunity from
*Surveys > Participations*.
