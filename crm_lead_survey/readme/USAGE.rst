On an opportunity form:

* **Start Survey** opens a wizard to start the survey of the opportunity's
  next stage, i.e. the stage that follows the current one in the stage
  sequence (only the stages of the opportunity's sales team are considered).
  When that stage requires a specific survey, it is filled in and cannot be
  changed; otherwise any survey can be picked. Confirming it creates the
  ``survey.user_input`` already linked to the opportunity and (optionally)
  opens the survey so it can be answered right away. Once the survey is
  submitted, the end page shows a **Close and return to the opportunity**
  button that brings the user back to the opportunity form (only shown to
  internal users, not to contacts answering through the survey link).
* The **Surveys** smart button shows only the participations of that
  opportunity.

To require a survey on a stage, go to *CRM > Configuration > Stages*, open the
stage and check **Survey required**. From then on, moving an opportunity to
that stage - from the form or by dragging it in the kanban - raises an error
unless at least one linked participation is in the *Completed* state. A survey
that was only started or is still in progress does not unlock the stage.

To require one survey in particular, also fill **Required survey** on the
stage. The opportunity then needs a completed participation *of that survey*;
completed participations of other surveys do not unlock the stage. Leave it
empty to accept any completed survey.

Participations can also be searched and grouped by opportunity from
*Surveys > Participations*.
