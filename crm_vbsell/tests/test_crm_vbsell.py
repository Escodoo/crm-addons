# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hmac
import json
from contextlib import contextmanager
from hashlib import sha256
from unittest.mock import patch

import requests
from werkzeug.wrappers import Response

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.crm_vbsell.controllers.webhook import VbsellWebhook, signature_matches
from odoo.addons.crm_vbsell.hooks import post_init_hook
from odoo.addons.queue_job.exception import RetryableJobError


class _HttpRequest:
    def __init__(self, data, headers):
        self._data = data
        self.headers = headers

    def get_data(self, *args, **kwargs):
        return self._data


class _Request:
    def __init__(self, httprequest, env):
        self.httprequest = httprequest
        self.env = env

    def make_response(self, data, headers=None, cookies=None, status=200):
        return Response(data, status=status, headers=headers)


class _ApiResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class TestCrmVbsell(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.reason = cls.env["crm.lost.reason"].create({"name": "VBSell lost"})
        cls.source = cls.env["utm.source"].create({"name": "VBSell"})
        cls.company.write(
            {
                "vbsell_enabled": True,
                "vbsell_api_base_url": "https://vbsell.test",
                "vbsell_api_key": "test-key",
                "vbsell_webhook_secret": "test-secret",
                "vbsell_company_uuid": "company-uuid",
                "vbsell_user_id": cls.env.user.id,
                "vbsell_source_id": cls.source.id,
                "vbsell_lost_reason_id": cls.reason.id,
                "vbsell_min_create_stage": "qualified",
            }
        )
        cls.stage_new = cls._make_stage("VBSell New", "new", 11)
        cls.stage_contacted = cls._make_stage("VBSell Contacted", "contacted", 12)
        cls.stage_qualified = cls._make_stage("VBSell Qualified", "qualified", 13)
        cls.stage_proposal = cls._make_stage("VBSell Proposal", "proposal", 14)
        cls.stage_won = cls._make_stage("VBSell Won", "won", 70, is_won=True)
        cls.stage_extra = cls.env["crm.stage"].create(
            {"name": "VBSell Extra", "sequence": 15}
        )

    @classmethod
    def _make_stage(cls, name, vbsell_stage, sequence, is_won=False):
        return cls.env["crm.stage"].create(
            {
                "name": name,
                "sequence": sequence,
                "vbsell_stage": vbsell_stage,
                "is_won": is_won,
            }
        )

    def _payload(
        self, new_stage, opportunity_id="opp-1", source=None, contact_id="c-1"
    ):
        payload = {
            "event": "opportunity.stage_changed",
            "data": {
                "newStage": new_stage,
                "previousStage": "new",
                "opportunity": {
                    "id": opportunity_id,
                    "companyId": "company-uuid",
                    "contactId": contact_id,
                },
            },
        }
        if source:
            payload["source"] = source
        return payload

    def _jobs(self, lead):
        return self.env["queue.job"].search(
            [("identity_key", "=", f"vbsell_stage_{lead.id}")]
        )

    def _write_now(self, lead, vals):
        return lead.with_context(queue_job__no_delay=True).write(vals)

    def _lead(self, stage, opportunity_id="opp-1", probability=10):
        # A salesperson is required. CRM clears company_id when the lead has
        # no user, no team and no partner, and the push is skipped.
        lead = (
            self.env["crm.lead"]
            .with_context(vbsell_skip_push=True)
            .create(
                {
                    "name": "Existing",
                    "type": "opportunity",
                    "company_id": self.company.id,
                    "user_id": self.env.user.id,
                    "stage_id": stage.id,
                    "vbsell_opportunity_id": opportunity_id,
                    "probability": probability,
                }
            )
        )
        self.assertEqual(lead.company_id, self.company)
        # create() keeps the context of the recordset. Drop the flag that
        # was only meant to silence the push during setup.
        return lead.with_context(vbsell_skip_push=False)

    def _contact_response(self, **overrides):
        data = {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+5511999999999",
            "vat": "BE0477472701",
        }
        data.update(overrides)
        data = {key: value for key, value in data.items() if value is not None}
        return _ApiResponse(200, {"data": data})

    def _post_raw(self, raw, secret="test-secret", header=None):
        if header is None:
            digest = hmac.new((secret or "").encode(), raw, sha256).hexdigest()
            header = "sha256=%s" % digest
        headers = {"X-Webhook-Signature": header} if header else {}
        http_request = _HttpRequest(raw, headers)
        fake = _Request(http_request, self.env)
        with patch("odoo.addons.crm_vbsell.controllers.webhook.request", fake):
            response = VbsellWebhook().opportunity()
        body = json.loads(response.get_data(as_text=True))
        return response.status_code, body

    def _post(self, payload, secret="test-secret", header=None):
        return self._post_raw(
            json.dumps(payload).encode(), secret=secret, header=header
        )

    def test_invalid_signature_is_rejected(self):
        status, body = self._post(self._payload("qualified"), header="sha256=dead")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "Invalid signature")
        self.assertFalse(
            self.env["crm.lead"].search([("vbsell_opportunity_id", "=", "opp-1")])
        )

    def test_api_source_does_not_write(self):
        lead = self._lead(self.stage_contacted)
        status, body = self._post(self._payload("won", source="api"))
        self.assertEqual(status, 200)
        self.assertEqual(body["reason"], "api_source")
        self.assertEqual(lead.stage_id, self.stage_contacted)

    def test_new_below_minimum_does_not_create(self):
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get"
        ) as get_contact:
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("new")
            )
        get_contact.assert_not_called()
        self.assertEqual(result["reason"], "below_minimum")
        self.assertFalse(
            self.env["crm.lead"].search([("vbsell_opportunity_id", "=", "opp-1")])
        )

    def test_qualified_creates_partner_and_lead(self):
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=self._contact_response(),
        ):
            status, body = self._post(self._payload("qualified"))
        self.assertEqual(status, 200)
        lead = self.env["crm.lead"].browse(body["lead_id"])
        self.assertEqual(lead.email_from, "ada@example.com")
        self.assertEqual(lead.partner_id.vat, "BE0477472701")
        self.assertEqual(lead.stage_id, self.stage_qualified)
        self.assertEqual(lead.source_id, self.source)
        self.assertEqual(lead.user_id, self.env.user)
        self.assertIn("https://vbsell.test/opportunities/opp-1", lead.description)

    def test_won_uses_won_stage(self):
        lead = self._lead(self.stage_qualified)
        self.env["crm.lead"]._vbsell_apply_webhook(self.company, self._payload("won"))
        self.assertTrue(lead.stage_id.is_won)
        self.assertEqual(lead.stage_id.vbsell_stage, "won")
        self.assertEqual(lead.probability, 100)

    def test_lost_calls_lost_flow(self):
        lead = self._lead(self.stage_qualified)
        self.env["crm.lead"]._vbsell_apply_webhook(self.company, self._payload("lost"))
        self.assertFalse(lead.active)
        self.assertEqual(lead.probability, 0)
        self.assertEqual(lead.lost_reason_id, self.reason)

    def test_unknown_stage_does_not_become_new(self):
        lead = self._lead(self.stage_contacted)
        with self.assertRaises(UserError):
            self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("negotiation")
            )
        self.assertEqual(lead.stage_id, self.stage_contacted)
        status, body = self._post(self._payload("negotiation"))
        self.assertEqual(status, 422)
        self.assertIn("negotiation", body["error"])
        self.assertEqual(lead.stage_id, self.stage_contacted)

    def test_skip_push_does_not_call_api(self):
        lead = self._lead(self.stage_contacted)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch"
        ) as patched:
            lead.with_context(vbsell_skip_push=True).write(
                {"stage_id": self.stage_qualified.id}
            )
        patched.assert_not_called()

    def test_mapped_stage_patches_vbsell(self):
        lead = self._lead(self.stage_contacted)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(200, {}),
        ) as patched:
            self._write_now(lead, {"stage_id": self.stage_qualified.id})
        patched.assert_called_once()
        self.assertEqual(patched.call_args.kwargs["json"], {"stage": "qualified"})
        self.assertIn("/api/v1/opportunities/opp-1", patched.call_args.args[0])
        self.assertEqual(
            patched.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-key",
        )

    def test_unmapped_stage_does_not_patch(self):
        lead = self._lead(self.stage_qualified)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch"
        ) as patched:
            lead.with_context(queue_job__no_delay=True).write(
                {"stage_id": self.stage_extra.id}
            )
        patched.assert_not_called()

    def test_won_stage_patches_won(self):
        lead = self._lead(self.stage_qualified)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(200, {}),
        ) as patched:
            lead.with_context(queue_job__no_delay=True).write(
                {"stage_id": self.stage_won.id}
            )
        self.assertEqual(patched.call_args.kwargs["json"], {"stage": "won"})

    def test_lost_patches_lost(self):
        lead = self._lead(self.stage_qualified)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(200, {}),
        ) as patched:
            lead.with_context(queue_job__no_delay=True).action_set_lost()
        self.assertEqual(patched.call_args.kwargs["json"], {"stage": "lost"})

    def test_api_failure_is_retried_and_posted_on_the_lead(self):
        lead = self._lead(self.stage_contacted)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(500, {}),
        ):
            lead.write({"stage_id": self.stage_qualified.id})
        self.assertEqual(lead.stage_id, self.stage_qualified)
        self.assertEqual(len(self._jobs(lead)), 1)
        # assertRaises rolls the savepoint back, which would drop the note.
        caught = None
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(500, {}),
        ):
            try:
                lead._vbsell_push_stage()
            except RetryableJobError as error:
                caught = error
        self.assertIsNotNone(caught)
        self.assertIn(
            "VBSell stage sync failed",
            " ".join(lead.message_ids.mapped("body")),
        )

    def test_retry_does_not_post_before_the_last_attempt(self):
        lead = self._lead(self.stage_contacted)
        lead.write({"stage_id": self.stage_qualified.id})
        job = self._jobs(lead)
        self.assertEqual(len(job), 1)
        caught = None
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(500, {}),
        ):
            try:
                lead.with_context(job_uuid=job.uuid)._vbsell_push_stage()
            except RetryableJobError as error:
                caught = error
        self.assertIsNotNone(caught)
        self.assertNotIn(
            "VBSell stage sync failed",
            " ".join(lead.message_ids.mapped("body")),
        )

    def test_pending_job_sends_the_latest_stage(self):
        lead = self._lead(self.stage_contacted)
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch"
        ) as patched:
            lead.write({"stage_id": self.stage_qualified.id})
            lead.write({"stage_id": self.stage_proposal.id})
        patched.assert_not_called()
        self.assertEqual(len(self._jobs(lead)), 1)
        self.assertEqual(self._jobs(lead).channel, "root.vbsell")
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(200, {}),
        ) as patched:
            lead._vbsell_push_stage()
        self.assertEqual(patched.call_args.kwargs["json"], {"stage": "proposal"})

    def test_stage_value_is_unique_per_team(self):
        with self.assertRaises(ValidationError):
            self._make_stage("VBSell New duplicate", "new", 16)

    def test_won_value_requires_won_stage(self):
        team = self.env["crm.team"].create({"name": "VBSell other team"})
        with self.assertRaises(ValidationError):
            self.env["crm.stage"].create(
                {
                    "name": "Not won",
                    "vbsell_stage": "won",
                    "is_won": False,
                    "team_id": team.id,
                }
            )

    def test_post_init_copies_legacy_column(self):
        lead = self._lead(self.stage_new, opportunity_id="keep-me")
        self.env.cr.execute(
            "ALTER TABLE crm_lead ADD COLUMN IF NOT EXISTS x_vbsell_id varchar"
        )
        self.env.cr.execute(
            "UPDATE crm_lead SET vbsell_opportunity_id = NULL, "
            "x_vbsell_id = %s WHERE id = %s",
            ("legacy-1", lead.id),
        )
        post_init_hook(self.env.cr, self.env.registry)
        lead.invalidate_recordset(["vbsell_opportunity_id"])
        self.assertEqual(lead.vbsell_opportunity_id, "legacy-1")

    def test_signature_requires_secret_and_prefix(self):
        raw = b"{}"
        self.assertFalse(signature_matches("", raw, "sha256=abc"))
        self.assertFalse(signature_matches("secret", raw, None))
        self.assertFalse(signature_matches("secret", raw, "md5=abc"))
        status, body = self._post(self._payload("qualified"), header="")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "Invalid signature")

    def test_invalid_json_is_rejected(self):
        status, body = self._post_raw(b"\xff")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Invalid JSON")
        status, body = self._post_raw(b"[]")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Invalid JSON")

    def test_unknown_company_is_rejected(self):
        payload = self._payload("qualified")
        payload["data"]["opportunity"]["companyId"] = "unknown-company"
        status, body = self._post(payload)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "Company not found")

    def test_missing_company_uuid_is_rejected(self):
        payload = self._payload("qualified")
        payload["data"]["opportunity"].pop("companyId")
        status, body = self._post(payload)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "Company not found")

    def test_unexpected_webhook_error_returns_500(self):
        with patch(
            "odoo.addons.crm_vbsell.models.crm_lead.CrmLead._vbsell_apply_webhook",
            side_effect=RuntimeError("boom"),
        ):
            status, body = self._post(self._payload("qualified"))
        self.assertEqual(status, 500)
        self.assertEqual(body["error"], "Webhook processing failed")

    def test_other_events_are_ignored(self):
        payload = self._payload("qualified")
        payload["event"] = "contact.updated"
        result = self.env["crm.lead"]._vbsell_apply_webhook(self.company, payload)
        self.assertEqual(result, {"status": "ignored", "reason": "event"})

    def test_payload_requires_opportunity_and_stage(self):
        missing_stage = self._payload("qualified", opportunity_id="opp-stage")
        missing_stage["data"]["newStage"] = False
        with self.assertRaises(UserError):
            self.env["crm.lead"]._vbsell_apply_webhook(self.company, missing_stage)
        missing_id = self._payload("qualified", opportunity_id="opp-id")
        missing_id["data"]["opportunity"]["id"] = False
        with self.assertRaises(UserError):
            self.env["crm.lead"]._vbsell_apply_webhook(self.company, missing_id)

    def test_lost_unknown_opportunity_is_ignored(self):
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get"
        ) as get_contact:
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("lost", opportunity_id="opp-lost-new")
            )
        get_contact.assert_not_called()
        self.assertEqual(result["reason"], "below_minimum")
        self.assertTrue(
            self.env["crm.lead"]._vbsell_reaches_minimum("qualified", False)
        )

    def test_create_without_contact_is_rejected(self):
        with self.assertRaises(UserError):
            self.env["crm.lead"]._vbsell_apply_webhook(
                self.company,
                self._payload(
                    "qualified", opportunity_id="opp-nocontact", contact_id=False
                ),
            )

    def test_won_create_sets_probability(self):
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=self._contact_response(),
        ):
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("won", opportunity_id="opp-won-new")
            )
        lead = self.env["crm.lead"].browse(result["lead_id"])
        self.assertTrue(lead.stage_id.is_won)
        self.assertEqual(lead.probability, 100)

    def test_existing_partner_is_reused_by_vat_then_email(self):
        vat_partner = self.env["res.partner"].create(
            {
                "name": "Existing VAT",
                "vat": "BE0477472701",
                "company_id": self.company.id,
            }
        )
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=self._contact_response(email="other@example.com"),
        ):
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("qualified", opportunity_id="opp-vat")
            )
        lead = self.env["crm.lead"].browse(result["lead_id"])
        self.assertEqual(lead.partner_id, vat_partner)

        email_partner = self.env["res.partner"].create(
            {
                "name": "Existing email",
                "email": "known@example.com",
                "company_id": self.company.id,
            }
        )
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=self._contact_response(
                name="Ignored", vat=None, email="known@example.com"
            ),
        ):
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("qualified", opportunity_id="opp-email")
            )
        lead = self.env["crm.lead"].browse(result["lead_id"])
        self.assertEqual(lead.partner_id, email_partner)

    def test_partner_name_falls_back_to_organization_then_placeholder(self):
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=self._contact_response(
                name=None, vat=None, email=None, organizationName="Analytical Engines"
            ),
        ):
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("qualified", opportunity_id="opp-org")
            )
        lead = self.env["crm.lead"].browse(result["lead_id"])
        self.assertEqual(lead.partner_id.name, "Analytical Engines")

        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=self._contact_response(
                name=None, vat=None, email=None, phone=None
            ),
        ):
            result = self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("qualified", opportunity_id="opp-noname")
            )
        lead = self.env["crm.lead"].browse(result["lead_id"])
        self.assertEqual(lead.partner_id.name, "VBSell contact")

    def test_team_stage_is_preferred(self):
        team = self.env["crm.team"].create({"name": "VBSell mapped team"})
        team_stage = self.env["crm.stage"].create(
            {
                "name": "Team proposal",
                "sequence": 21,
                "vbsell_stage": "proposal",
                "team_id": team.id,
            }
        )
        lead_model = self.env["crm.lead"]
        self.assertEqual(lead_model._vbsell_find_stage(team, "proposal"), team_stage)
        self.assertEqual(
            lead_model._vbsell_find_stage(self.env["crm.team"], "proposal"),
            self.stage_proposal,
        )

    def test_missing_stage_mapping_is_rejected(self):
        self.stage_proposal.vbsell_stage = False
        lead = self._lead(self.stage_contacted, opportunity_id="opp-unmap")
        with self.assertRaises(UserError):
            self.env["crm.lead"]._vbsell_apply_webhook(
                self.company, self._payload("proposal", opportunity_id="opp-unmap")
            )
        self.assertEqual(lead.stage_id, self.stage_contacted)

    def test_won_mapping_must_be_a_won_stage(self):
        with self.assertRaises(UserError):
            self.env["crm.lead"]._vbsell_check_stage(self.stage_qualified, "won")

    def test_repeated_stage_and_lost_are_idempotent(self):
        lead = self._lead(self.stage_qualified, opportunity_id="opp-same")
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("qualified", opportunity_id="opp-same")
        )
        self.assertEqual(lead.stage_id, self.stage_qualified)
        self.assertEqual(lead.probability, 10)

        won = self._lead(
            self.stage_won, opportunity_id="opp-won-again", probability=100
        )
        self.assertEqual(won.stage_id, self.stage_won)
        self.assertEqual(won.probability, 100)
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("won", opportunity_id="opp-won-again")
        )
        self.assertEqual(won.probability, 100)

        lost = self._lead(self.stage_qualified, opportunity_id="opp-lost-again")
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("lost", opportunity_id="opp-lost-again")
        )
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("lost", opportunity_id="opp-lost-again")
        )
        self.assertFalse(lost.active)
        self.assertEqual(lost.probability, 0)

    def test_reactivate_lost_lead_restores_probability(self):
        lead = self._lead(self.stage_qualified, opportunity_id="opp-back")
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("lost", opportunity_id="opp-back")
        )
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("qualified", opportunity_id="opp-back")
        )
        self.assertTrue(lead.active)
        self.assertEqual(lead.stage_id, self.stage_qualified)

        active = self._lead(self.stage_contacted, opportunity_id="opp-zero")
        active.with_context(vbsell_skip_push=True).write({"probability": 0})
        self.assertTrue(active.active)
        self.assertEqual(active.probability, 0)
        self.env["crm.lead"]._vbsell_apply_webhook(
            self.company, self._payload("qualified", opportunity_id="opp-zero")
        )
        self.assertEqual(active.stage_id, self.stage_qualified)
        self.assertEqual(active.probability, 10)

    def test_push_is_skipped_without_a_target(self):
        unlinked = (
            self.env["crm.lead"]
            .with_context(vbsell_skip_push=True)
            .create(
                {
                    "name": "Local only",
                    "type": "opportunity",
                    "company_id": self.company.id,
                    "user_id": self.env.user.id,
                    "stage_id": self.stage_contacted.id,
                }
            )
            .with_context(vbsell_skip_push=False)
        )
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch"
        ) as patched:
            unlinked.write({"stage_id": self.stage_qualified.id})
            unlinked._vbsell_push_stage()
        patched.assert_not_called()

        linked = self._lead(self.stage_contacted, opportunity_id="opp-skip")
        linked.with_context(vbsell_skip_push=True)._vbsell_push_if_changed("new")
        linked.with_context(vbsell_skip_push=True)._vbsell_push_stage()

        self.company.vbsell_enabled = False
        linked._vbsell_push_if_changed("new")
        linked._vbsell_push_stage()
        self.company.vbsell_enabled = True

        orphan = self._lead(self.stage_contacted, opportunity_id="opp-orphan")
        orphan.write(
            {
                "user_id": False,
                "team_id": False,
                "partner_id": False,
                "stage_id": self.stage_qualified.id,
            }
        )
        self.assertFalse(orphan.company_id)
        self.assertFalse(self._jobs(orphan))
        orphan._vbsell_push_stage()

        plain = self._lead(self.stage_extra, opportunity_id="opp-plain")
        plain._vbsell_push_stage()

    def test_retry_counter_decides_the_chatter_note(self):
        lead = self._lead(self.stage_contacted, opportunity_id="opp-retry-count")
        self.assertTrue(
            lead.with_context(job_uuid="missing-job")._vbsell_push_is_last_attempt()
        )
        lead.write({"stage_id": self.stage_qualified.id})
        job = self._jobs(lead)
        job.write({"max_retries": 0})
        self.assertFalse(
            lead.with_context(job_uuid=job.uuid)._vbsell_push_is_last_attempt()
        )
        job.write({"max_retries": 5, "retry": 4})
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            return_value=_ApiResponse(500, {}),
        ):
            try:
                lead.with_context(job_uuid=job.uuid)._vbsell_push_stage()
            except RetryableJobError as error:
                caught = error
            else:
                caught = None
        self.assertIsNotNone(caught)
        self.assertIn(
            "VBSell stage sync failed",
            " ".join(lead.message_ids.mapped("body")),
        )

    def test_sync_failure_can_be_posted_outside_the_job_cursor(self):
        lead = self._lead(self.stage_contacted, opportunity_id="opp-cursor")

        @contextmanager
        def same_cursor():
            yield self.env.cr

        with patch.object(self.env.registry, "cursor", lambda: same_cursor()):
            lead._vbsell_post_sync_failure(UserError("separate cursor"))
        self.assertIn(
            "separate cursor",
            " ".join(lead.message_ids.mapped("body")),
        )

    def test_sync_failure_post_error_is_logged(self):
        lead = self._lead(self.stage_contacted, opportunity_id="opp-chatter")
        with patch.object(
            type(lead), "message_post", side_effect=RuntimeError("chatter down")
        ), self.assertLogs(
            "odoo.addons.crm_vbsell.models.crm_lead", level="ERROR"
        ) as logs:
            lead._vbsell_post_sync_failure(UserError("boom"))
        self.assertIn("could not post the sync failure", " ".join(logs.output))

    def test_company_uuid_is_unique(self):
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                {
                    "name": "VBSell duplicate",
                    "vbsell_company_uuid": self.company.vbsell_company_uuid,
                }
            )

    def test_api_errors_are_reported(self):
        api = self.env["vbsell.api"]
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            side_effect=requests.RequestException("down"),
        ), self.assertRaises(UserError):
            api.get_contact(self.company, "c-1")
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=_ApiResponse(404, {}),
        ), self.assertRaises(UserError):
            api.get_contact(self.company, "c-1")
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=_ApiResponse(200, []),
        ), self.assertRaises(UserError):
            api.get_contact(self.company, "c-1")
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.get",
            return_value=_ApiResponse(200, {"data": ["not", "a", "contact"]}),
        ), self.assertRaises(UserError):
            api.get_contact(self.company, "c-1")
        with patch(
            "odoo.addons.crm_vbsell.models.vbsell_api.requests.patch",
            side_effect=requests.RequestException("down"),
        ), self.assertRaises(UserError):
            api.patch_opportunity(self.company, "opp-1", "qualified")

    def _settings_vals(self, **overrides):
        vals = {
            "company_id": self.company.id,
            "vbsell_enabled": True,
            "vbsell_api_base_url": "https://vbsell.test",
            "vbsell_api_key": "test-key",
            "vbsell_webhook_secret": "test-secret",
            "vbsell_company_uuid": "company-uuid",
            "vbsell_user_id": self.env.user.id,
            "vbsell_source_id": self.source.id,
            "vbsell_lost_reason_id": self.reason.id,
            "vbsell_min_create_stage": "qualified",
        }
        vals.update(overrides)
        return vals

    def test_settings_form_loads_the_company_configuration(self):
        values = self.env["res.config.settings"].default_get(
            [
                "vbsell_enabled",
                "vbsell_company_uuid",
                "vbsell_api_key",
                "vbsell_webhook_secret",
                "vbsell_user_id",
            ]
        )
        self.assertTrue(values["vbsell_enabled"])
        self.assertEqual(values["vbsell_company_uuid"], "company-uuid")
        self.assertEqual(values["vbsell_api_key"], "test-key")
        self.assertEqual(values["vbsell_webhook_secret"], "test-secret")
        self.assertEqual(values["vbsell_user_id"], self.env.user.id)

    def test_blank_settings_save_keeps_the_company_configuration(self):
        self.env["res.config.settings"].create(
            self._settings_vals(
                vbsell_enabled=False,
                vbsell_api_base_url=False,
                vbsell_api_key=False,
                vbsell_webhook_secret=False,
                vbsell_company_uuid=False,
                vbsell_user_id=False,
                vbsell_source_id=False,
                vbsell_lost_reason_id=False,
                vbsell_min_create_stage=False,
            )
        )
        self.assertTrue(self.company.vbsell_enabled)
        self.assertEqual(self.company.vbsell_api_key, "test-key")
        self.assertEqual(self.company.vbsell_webhook_secret, "test-secret")
        self.assertEqual(self.company.vbsell_company_uuid, "company-uuid")
        self.assertEqual(self.company.vbsell_user_id, self.env.user)
        self.assertEqual(self.company.vbsell_min_create_stage, "qualified")

    def test_disabling_settings_keeps_the_other_company_values(self):
        self.env["res.config.settings"].create(
            self._settings_vals(vbsell_enabled=False)
        )
        self.assertFalse(self.company.vbsell_enabled)
        self.assertEqual(self.company.vbsell_company_uuid, "company-uuid")
        self.assertEqual(self.company.vbsell_api_key, "test-key")

    def test_blank_secret_keeps_the_stored_key(self):
        self.env["res.config.settings"].create(
            self._settings_vals(
                vbsell_api_key=False,
                vbsell_webhook_secret="",
                vbsell_api_base_url="https://vbsell.example",
            )
        )
        self.assertEqual(self.company.vbsell_api_key, "test-key")
        self.assertEqual(self.company.vbsell_webhook_secret, "test-secret")
        self.assertEqual(self.company.vbsell_api_base_url, "https://vbsell.example")

    def test_settings_save_replaces_the_api_key(self):
        self.env["res.config.settings"].create(
            self._settings_vals(
                vbsell_api_key="rotated-key",
                vbsell_webhook_secret="rotated-secret",
            )
        )
        self.assertEqual(self.company.vbsell_api_key, "rotated-key")
        self.assertEqual(self.company.vbsell_webhook_secret, "rotated-secret")
