This module shows the **Mobile** field of CRM opportunities next to the phone
number, both on the opportunity form and on the kanban quick create form.

When the contact (``partner_id``) of an opportunity is set or changed, the
mobile is filled from the contact's mobile, as Odoo already does for leads. If
the contact has no mobile, the opportunity keeps the mobile it already had. The
value is stored on the opportunity, and editing it does not change the contact.
