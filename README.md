# Loan underwriting copilot (MVP)

A local run of the seven-agent loan case. Ratios, covenant tests, customer lookup, policy search, and the approval route are all tool results. With no Azure settings, the agents use those tool results directly so you can test the case flow on this machine.

## Run a case

From `AzTraining/finUseCase`. On this PC the `python` command is not on PATH, so use `py -3`. Install into a virtual environment so this project's packages stay separate from your other Python tools:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\run_case.py --case case_001_strong --auto-approve
```

The other sample cases are listed below. Omit `--auto-approve` to type each of the three review decisions yourself.

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python scripts\run_functional.py
```

`data/catalog.json` is the expected result for every sample folder. `run_functional.py` runs each folder and prints the grade, recommendation, and approver. Pytest checks that same catalog, plus reviewer revise, decline, send-back, the revision cap, the HTTP API, and the five MCP tool servers.

## What you should see

| Case | Tool result | Approver if the reviewers approve |
|---|---|---|
| `case_001_strong` | Covenants pass. Recommendation approve, grade 3 | Senior Credit Officer |
| `case_002_borderline` | Pro-forma leverage breaks the 3.5x cap | Credit Committee |
| `case_003_breach` | DSCR, leverage, current ratio, and interest coverage all fail | Credit Committee, recommendation decline |
| `case_004_name_mismatch` | Same numbers as the strong case. Request name does not match the customer record | Senior Credit Officer |
| `case_005_credit_officer` | $750,000 loan, covenants pass | Credit Officer |
| `case_006_board` | $28,000,000 loan, covenants pass | Board Credit Committee |
| `case_007_missing_credit` | Credit report file is absent. Case stops | — |
| `case_008_unknown_customer` | Borrower `BRW-9999` is not in `data/borrowers.json`. Case stops | — |

Customers for the new complete cases are `BRW-4100` Maple Street Bakery LLC and `BRW-5500` Summit Steel Holdings in `data/borrowers.json`. `scripts/seed_cosmos.py` loads that file when Cosmos is turned on.

`--auto-approve` records an approval at every checkpoint, including when the risk agent recommends decline. That lets you see the recorded decision separately from the recommendation.

## Optional Azure services

Copy `.env.example` to `.env` and fill in only what you have.

- `USE_KEY_VAULT=true` reads `az-openai-endpoint` and `az-openai-apikey` from `clinic-kv-tc-training`, exactly as the existing `rag` project does. Run `az login` first on your workstation. In Azure, the app uses its managed identity. The narrative deployment is `gpt-6.1-terra`; numbers still come from the tools.
- Direct `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` values override Key Vault when you need a different test resource.
- `USE_COSMOS=true` reads customers from Cosmos. With `USE_KEY_VAULT=true`, the account comes from `cosmos-cxn-str` and `cosmos-cxn-key` in `clinic-kv-tc-training`, the same secrets the `rag` project uses. `.\.venv\Scripts\python scripts\seed_cosmos.py` loads `data/borrowers.json` into database `loan_underwriting`, container `customers`. Leave `USE_COSMOS=false` and the case uses `data/borrowers.json`.
- `REDIS_URL` (for example `redis://localhost:6379` after `docker compose up redis`) stores the audit trail and decisions in Redis instead of `data/runtime/store.json`.
- `USE_AZURE_SEARCH=true` plus the Search settings queries the two indexes. Until then, search reads `data/policies` and `data/precedents`.

## MCP servers

The five MCP servers expose every tool the case uses. The case runner calls those functions in-process. Start a server when you want the same tool over streamable HTTP:

| Server | Tools |
|---|---|
| borrower (8101) | `get_borrower_profile`, `search_borrowers` |
| financials (8102) | `calculate_ratios`, `pro_forma_debt_service` |
| covenants (8103) | `list_standard_covenants`, `test_covenants` |
| workflow (8104) | `create_case`, `update_status`, `get_case_status`, `get_audit_trail` |
| approval (8105) | `get_authority_matrix`, `lookup_authority`, `record_hitl_decision`, `record_final_decision`, `get_decision` |

```powershell
.\.venv\Scripts\python scripts\run_mcp.py borrower
.\.venv\Scripts\python scripts\run_mcp.py financials
.\.venv\Scripts\python scripts\run_mcp.py covenants
.\.venv\Scripts\python scripts\run_mcp.py workflow
.\.venv\Scripts\python scripts\run_mcp.py approval
```

Ports are 8101 through 8105.

## HTTP API

```powershell
.\.venv\Scripts\python -m uvicorn loan_copilot.api.main:app --app-dir src --port 8080
```

`POST /cases` with `{"sample_case": "case_001_strong", "auto_approve": true}` runs a case. Leave `auto_approve` false, then post each decision to `/cases/{case_id}/decisions`.
