.PHONY: setup test test-live plan apply secret-scan lint verify-blocking-push

PY := .venv/bin/python
REPO := ismail-ougamane/GitHub_Analytics_Data_Engineering_Flow

setup:  ## create venv and install deps
	uv venv .venv --python 3.14
	uv pip install --python .venv/bin/python 'requests>=2.32' 'pytest>=8' 'ruff>=0.6'
	@echo "setup done"

test:  ## offline unit tests (must pass on every PR)
	$(PY) -m pytest tests/unit

test-live:  ## acceptance criteria against the real repository (needs gh auth)
	GOVERNANCE_LIVE=1 GH_TOKEN=$$(gh auth token) $(PY) -m pytest tests/live -m live -v

plan:  ## drift report: desired (config) vs actual (GitHub)
	$(PY) scripts/apply_governance.py --plan

apply:  ## converge GitHub to config/governance.toml
	$(PY) scripts/apply_governance.py --apply

secret-scan:  ## must be clean before any push
	$(PY) -m pytest tests/unit/test_no_secrets.py -v

lint:
	.venv/bin/ruff check src tests scripts

verify-blocking-push:  ## AC-3 negative probe: a real push to main MUST fail
	bash scripts/verify_blocking_push.sh
