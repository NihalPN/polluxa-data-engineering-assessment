# Part 1 - Integration Baseline & Synthetic Architecture
**Candidate:** Muhammed Nihal P. N.



## 1. Execution Declaration & Methodology
* **Execution Mode:** Synthetic Environment / API Workflow Mock
* **Authorization:** Alternative assessment pathway confirmed by Polluxa recruitment via email on 19 August 2026.
* **Methodology:** To maintain strict account security while demonstrating absolute protocol adherence, the 7-step integration workflow is modeled programmatically. Instead of live interface clicks, this document defines the theoretical API payloads, authentication states, constraint configurations, and the exact synthetic data schema generated for Parts 2–8.

## 2. Workflow State Definitions (Steps 1–5)
### Credential Provisioning (Session Cookie Method)
The system assumes a `POST` request to the backend integration endpoint using the recommended Session Cookie authorization method.

```json
// POST /api/v1/integrations/linkedin/connect
{
  "integration_type": "LINKEDIN_AGENT",
  "auth_method": "SESSION_COOKIE",
  "credentials": {
    "li_at": "**********_sanitized_**********"
  },
  "timestamp": "2026-08-21T10:00:00Z"
}