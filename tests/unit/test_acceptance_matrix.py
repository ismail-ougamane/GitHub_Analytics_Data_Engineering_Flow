"""Meta-test: every acceptance criterion in the ticket doc must have a live
test. Deleting an AC from the test suite without updating the ticket (or vice
versa) fails here — acceptance criteria cannot silently rot.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TICKET = REPO_ROOT / "docs" / "tickets" / "TICKET-001-protected-main-branch.md"

# AC id (as written in the ticket) -> live test module that proves it
ACCEPTANCE_MATRIX = {
    "AC-1": "test_ac1_repository.py",
    "AC-1b": "test_ac1b_collaborators.py",
    "AC-2": "test_ac2_reviews.py",
    "AC-3": "test_ac3_no_direct_push.py",
    "AC-4": "test_ac4_idempotent_apply.py",
}


class TestAcceptanceMatrix:
    def test_ticket_doc_exists(self):
        assert TICKET.exists(), f"missing ticket doc: {TICKET}"

    def test_every_ac_has_a_live_test(self):
        text = TICKET.read_text()
        missing = []
        for ac_id, module in ACCEPTANCE_MATRIX.items():
            assert ac_id in text, f"ticket doc no longer mentions {ac_id}"
            if not (REPO_ROOT / "tests" / "live" / module).exists():
                missing.append(f"{ac_id} -> tests/live/{module}")
        assert missing == [], "ACs without tests:\n" + "\n".join(missing)

    def test_no_orphan_live_tests(self):
        """A live test that no AC maps to is dead weight or a hidden AC."""
        for path in (REPO_ROOT / "tests" / "live").glob("test_*.py"):
            assert path.name in ACCEPTANCE_MATRIX.values(), (
                f"{path.name} is not mapped to any AC in {ACCEPTANCE_MATRIX}"
            )
