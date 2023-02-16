from odoo.tests.common import TransactionCase


class TestCrmSLA(TransactionCase):
    def setUp(self):
        super(TestCrmSLA, self).setUp()
        self.team = self.env["crm.team"].create(
            {
                "name": "Test Sales Team",
                "use_sla": True,
            }
        )

        self.stage_target_1 = self.env["crm.stage"].create(
            {
                "name": "Stage 1",
                "sequence": 20,
            }
        )
        self.partner_1 = self.env["res.partner"].create({"name": "Test Partner 1"})
        self.partner_2 = self.env["res.partner"].create({"name": "Test Partner 2"})

        self.sla = self.env["crm.sla"].create(
            {
                "name": "Test SLA",
                "team_id": self.team.id,
                "partner_ids": [(4, self.partner_1.id)],
                "duration": 8,
                "target_stage_id": self.stage_target_1.id,
            }
        )

        self.lead_1 = self.env["crm.lead"].create(
            {
                "name": "Test Lead 1",
                "team_id": self.team.id,
                "partner_id": self.partner_1.id,
            }
        )
        self.lead_2 = self.env["crm.lead"].create(
            {
                "name": "Test Lead 2",
                "team_id": self.team.id,
                "partner_id": self.partner_2.id,
            }
        )
        self.lead_1._sync_sla_lines()
        self.lead_2._sync_sla_lines()

    def test_sla_lead_ids(self):

        self.assertIn(
            self.lead_1, self.sla.lead_ids, "Test Lead 1 should be in SLA Lead IDs"
        )
        self.assertNotIn(
            self.lead_2, self.sla.lead_ids, "Test Lead 2 should not be in SLA Lead IDs"
        )

    def test_sla_reached_date(self):
        # Move lead 1 to target stage after 5 days (within SLA duration)
        self.lead_1.write({"stage_id": self.stage_target_1.id})
        self.lead_1._sync_sla_lines()
        self.assertEqual(
            len(self.sla.sla_line_ids),
            1,
            "SLA Line should be created for the Lead 1",
        )
        self.assertTrue(
            self.sla.sla_line_ids.reached_date,
            "Date reached should be set for the Lead 1 SLA Line",
        )
