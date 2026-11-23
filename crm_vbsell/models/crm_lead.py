# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.queue_job.exception import RetryableJobError

from ..const import VBSELL_KNOWN_STAGES, VBSELL_STAGE_ORDER

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    vbsell_opportunity_id = fields.Char(
        string="VBSell Opportunity",
        copy=False,
        index=True,
        tracking=True,
    )

    _sql_constraints = [
        (
            "vbsell_opportunity_company_uniq",
            "unique(vbsell_opportunity_id, company_id)",
            "This VBSell opportunity is already linked to another lead.",
        )
    ]

    def write(self, vals):
        tracked = {"stage_id", "active", "probability"}
        previous = {}
        if not self.env.context.get("vbsell_skip_push") and tracked.intersection(vals):
            previous = {lead.id: lead._vbsell_outbound_stage() for lead in self}
        result = super().write(vals)
        if previous:
            for lead in self:
                lead._vbsell_push_if_changed(previous.get(lead.id))
        return result

    def _vbsell_outbound_stage(self):
        self.ensure_one()
        if not self.active and self.probability == 0:
            return "lost"
        stage = self.stage_id
        if stage.is_won:
            return "won" if stage.vbsell_stage else False
        return stage.vbsell_stage or False

    def _vbsell_push_if_changed(self, previous):
        self.ensure_one()
        if self.env.context.get("vbsell_skip_push") or not self.vbsell_opportunity_id:
            return
        company = self.company_id
        if not company or not company.vbsell_enabled:
            return
        current = self._vbsell_outbound_stage()
        if not current or current == previous:
            return
        self.with_delay(
            description=_("Push the VBSell stage of %(lead)s", lead=self.display_name),
            identity_key=self._vbsell_push_identity_key(),
        )._vbsell_push_stage()

    def _vbsell_push_identity_key(self):
        self.ensure_one()
        return f"vbsell_stage_{self.id}"

    def _vbsell_push_stage(self):
        """Send the stage that is current when the job runs.

        A later change reuses the pending job, so the stage is not captured
        when the job is created.
        """
        self.ensure_one()
        if self.env.context.get("vbsell_skip_push") or not self.vbsell_opportunity_id:
            return
        company = self.company_id
        if not company or not company.vbsell_enabled:
            return
        stage = self._vbsell_outbound_stage()
        if not stage:
            return
        try:
            self.env["vbsell.api"].patch_opportunity(
                company.sudo(), self.vbsell_opportunity_id, stage
            )
        except Exception as error:
            _logger.exception("VBSell stage sync failed for lead %s", self.id)
            if self._vbsell_push_is_last_attempt():
                self._vbsell_post_sync_failure(error)
            raise RetryableJobError(str(error)) from error

    def _vbsell_push_is_last_attempt(self):
        """True when this run will not be retried by the job queue."""
        job_uuid = self.env.context.get("job_uuid")
        if not job_uuid:
            return True
        job = self.env["queue.job"].sudo().search([("uuid", "=", job_uuid)], limit=1)
        if not job:
            return True
        if not job.max_retries:
            return False
        return (job.retry or 0) + 1 >= job.max_retries

    def _vbsell_post_sync_failure(self, error):
        """Post the failure on the lead.

        The job runner rolls the job transaction back after a retryable
        error and after the final failure. A note posted there disappears,
        so the committed note uses its own cursor when the lead is already
        visible. Tests that have not committed the lead fall back to the
        current cursor.
        """
        self.ensure_one()
        body = _("VBSell stage sync failed: %(error)s", error=error)
        try:
            if not self._vbsell_post_failure_outside_job(body):
                self.with_context(vbsell_skip_push=True).message_post(body=body)
        except Exception:
            _logger.exception(
                "VBSell could not post the sync failure on lead %s", self.id
            )

    def _vbsell_post_failure_outside_job(self, body):
        self.ensure_one()
        with self.env.registry.cursor() as cr:
            lead = self.with_env(self.env(cr=cr))
            if not lead.exists():
                return False
            lead.with_context(vbsell_skip_push=True).message_post(body=body)
        return True

    def _vbsell_apply_webhook(self, company, payload):
        if payload.get("source") == "api":
            return {"status": "ignored", "reason": "api_source"}
        if payload.get("event") != "opportunity.stage_changed":
            return {"status": "ignored", "reason": "event"}
        data = payload.get("data") or {}
        new_stage = data.get("newStage")
        opportunity = data.get("opportunity") or {}
        opportunity_id = opportunity.get("id")
        if not opportunity_id or not new_stage:
            raise UserError(
                _("VBSell payload is missing the opportunity id or the new stage.")
            )
        opportunity_id = str(opportunity_id)
        if new_stage not in VBSELL_KNOWN_STAGES:
            raise UserError(_("Unknown VBSell stage: %(stage)s", stage=new_stage))
        lead = self.with_context(active_test=False).search(
            [
                ("vbsell_opportunity_id", "=", opportunity_id),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not lead:
            if not self._vbsell_reaches_minimum(
                new_stage, company.vbsell_min_create_stage
            ):
                return {"status": "ignored", "reason": "below_minimum"}
            lead = self._vbsell_create_lead(
                company, opportunity, new_stage, opportunity_id
            )
        else:
            self._vbsell_apply_stage(lead, company, new_stage)
        return {"status": "ok", "lead_id": lead.id}

    def _vbsell_reaches_minimum(self, new_stage, minimum):
        try:
            rank = VBSELL_STAGE_ORDER.index(new_stage)
            floor = VBSELL_STAGE_ORDER.index(minimum or "qualified")
        except ValueError:
            return False
        return rank >= floor

    def _vbsell_find_stage(self, team, vbsell_stage):
        stage_model = self.env["crm.stage"]
        if team:
            stage = stage_model.search(
                [
                    ("vbsell_stage", "=", vbsell_stage),
                    ("team_id", "=", team.id),
                ],
                limit=1,
            )
            if stage:
                return stage
        return stage_model.search(
            [
                ("vbsell_stage", "=", vbsell_stage),
                ("team_id", "=", False),
            ],
            limit=1,
        )

    def _vbsell_check_stage(self, stage, vbsell_stage):
        if not stage:
            raise UserError(
                _(
                    "No CRM stage is mapped to VBSell stage %(stage)s.",
                    stage=vbsell_stage,
                )
            )
        if vbsell_stage == "won" and not stage.is_won:
            raise UserError(
                _("The CRM stage mapped to VBSell Won must be marked as won.")
            )

    def _vbsell_partner(self, company, contact):
        partner_model = self.env["res.partner"].with_context(no_vat_validation=True)
        vat = contact.get("vat") or False
        email = contact.get("email") or False
        company_domain = [("company_id", "in", [False, company.id])]
        partner = partner_model.browse()
        if vat:
            partner = partner_model.search(
                company_domain + [("vat", "=", vat)], limit=1
            )
        if not partner and email:
            partner = partner_model.search(
                company_domain + [("email", "=ilike", email)],
                limit=1,
            )
        if partner:
            return partner
        name = (
            contact.get("name")
            or contact.get("organizationName")
            or _("VBSell contact")
        )
        return partner_model.create(
            {
                "name": name,
                "email": email,
                "phone": contact.get("phone") or False,
                "vat": vat,
                "company_id": company.id,
            }
        )

    def _vbsell_create_lead(self, company, opportunity, new_stage, opportunity_id):
        contact_id = opportunity.get("contactId")
        if not contact_id:
            raise UserError(_("VBSell opportunity has no contact."))
        contact = self.env["vbsell.api"].get_contact(company, contact_id)
        partner = self._vbsell_partner(company, contact)
        user = company.vbsell_user_id
        team = user.sale_team_id if user else self.env["crm.team"]
        stage = self._vbsell_find_stage(team, new_stage)
        self._vbsell_check_stage(stage, new_stage)
        base = (company.vbsell_api_base_url or "").rstrip("/")
        url = f"{base}/opportunities/{opportunity_id}"
        safe_url = escape(url)
        vals = {
            "name": partner.name,
            "type": "opportunity",
            "partner_id": partner.id,
            "email_from": contact.get("email") or False,
            "phone": contact.get("phone") or False,
            "company_id": company.id,
            "user_id": user.id if user else False,
            "team_id": team.id if team else False,
            "source_id": company.vbsell_source_id.id or False,
            "vbsell_opportunity_id": opportunity_id,
            "description": Markup('<p><a href="%s">%s</a></p>') % (safe_url, safe_url),
            "stage_id": stage.id,
        }
        if new_stage == "won":
            vals["probability"] = 100
        return self.with_context(vbsell_skip_push=True).create(vals)

    def _vbsell_apply_stage(self, lead, company, new_stage):
        lead = lead.with_context(vbsell_skip_push=True)
        if new_stage == "lost":
            if not lead.active and lead.probability == 0:
                return
            reason = company.vbsell_lost_reason_id
            values = {"lost_reason_id": reason.id} if reason else {}
            lead.action_set_lost(**values)
            return
        if not lead.active:
            lead.action_unarchive()
        stage = self._vbsell_find_stage(lead.team_id, new_stage)
        self._vbsell_check_stage(stage, new_stage)
        already_there = lead.stage_id == stage and lead.probability != 0
        if already_there and (new_stage != "won" or lead.probability == 100):
            return
        values = {"stage_id": stage.id, "lost_reason_id": False}
        if new_stage == "won":
            values["probability"] = 100
        elif lead.probability == 0:
            # Probability 0 is the lost flag even when the lead is active.
            values["probability"] = 10
        lead.write(values)
