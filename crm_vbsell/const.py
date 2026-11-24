# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

VBSELL_OPEN_STAGES = [
    ("new", "New"),
    ("contacted", "Contacted"),
    ("qualified", "Qualified"),
    ("proposal", "Proposal"),
    ("won", "Won"),
]
VBSELL_STAGE_ORDER = [key for key, _label in VBSELL_OPEN_STAGES]
VBSELL_KNOWN_STAGES = set(VBSELL_STAGE_ORDER) | {"lost"}
WEBHOOK_EVENT = "opportunity.stage_changed"
API_SOURCE = "api"
REQUEST_TIMEOUT = 10
