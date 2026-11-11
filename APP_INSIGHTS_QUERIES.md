# Application Insights queries for the loan copilot

Run these in the Azure portal: open the Application Insights resource, then **Logs**. Paste one query at a time and select **Run**.

These queries parse against the resource. They have not yet returned rows for this project. If query 1 returns nothing after you run a case, export is not reaching the resource you are viewing. See the notes at the end.

---

## 1. Recent app log lines

Shows whether Azure Monitor export started and whether Cosmos, Key Vault, or Redis logged anything.

```kusto
traces
| where timestamp > ago(2h)
| where message has 'Azure Monitor' or message has 'Cosmos' or message has 'Key Vault' or message has 'Redis'
| project timestamp, severityLevel, message
| order by timestamp desc
```

## 2. Exceptions grouped by type

Shows which exceptions happened and how often.

```kusto
exceptions
| where timestamp > ago(24h)
| summarize occurrences = count() by type, outerMessage
| order by occurrences desc
```

## 3. Calls the app made, by target

Shows calls to Cosmos, Redis, Search, and OpenAI, if the SDK is instrumented. Failures and average duration are included.

```kusto
dependencies
| where timestamp > ago(24h)
| summarize calls = count(), failures = countif(success == false), avg_ms = avg(duration) by type, target
| order by calls desc
```

## 4. Where the app fell back to local data

Shows the warnings logged when Cosmos or Key Vault was unavailable and the app used local files.

```kusto
traces
| where timestamp > ago(24h)
| where message has 'Using data/borrowers.json' or message has 'Key Vault' or message has 'was not loaded'
| project timestamp, severityLevel, message
| order by timestamp desc
```

## 5. Everything logged during one run

Replace the two timestamps with a time from one case. Get that time from the `at` values in the audit trail:

```powershell
uv run scripts/show_case.py case_001_strong-cb656f36
```

```kusto
traces
| where timestamp between (datetime(2026-11-09T12:22:00Z) .. datetime(2026-11-09T12:24:00Z))
| project timestamp, severityLevel, message
| order by timestamp asc
```

---

## Notes

- **No rows from query 1:** Check that the run log shows `Azure Monitor export is on`. Then check that `APPLICATIONINSIGHTS_CONNECTION_STRING` (loaded from Key Vault secret `app-insights-cxn-str`) points to the resource you are viewing. Telemetry can take a few minutes to appear.
- **No rows from query 3:** The SDK may not instrument the HTTP client the app uses for OpenAI or Redis. Cosmos and Search calls may still appear. Lack of rows is not an error by itself.
- **Time window in query 5:** Use the `at` value of a real run. Times are UTC. Portal time may be shown in your local zone.
- **Message matching:** Queries use `has` on the message text. The app does not attach a `case_id` to telemetry, so match on time, not on case id.
