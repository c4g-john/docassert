---
kind: charter
id: AUR-charter
project: PRJ-001-AUR
title: Aurora — Customer Onboarding Overhaul
sponsor: jordan.lee
budget:
  amount: 1200000
  currency: USD
dates:
  created: 2026-01-15
  target: 2026-12-15
status: approved
---

## Objective

Cut median customer onboarding time from 14 days to under 2 days by replacing
the manual, ticket-driven setup process with a self-serve flow, so new
customers reach first value in their first working session rather than their
third week.

## Success Criteria

- Median onboarding time (p50) drops below 48 hours.
- Onboarding CSAT rises above 4.5 / 5.
- Manual setup tickets fall by at least 80%.
- Self-serve completion rate reaches 90% within 30 days of launch.

## Scope

In scope: the self-serve onboarding flow, data migration from the legacy setup
tool, and the customer-facing progress tracker. Out of scope: billing changes,
the mobile app, and enterprise SSO (tracked separately).

## Milestones

- MVP self-serve flow — 2026-09-30
- General availability — 2026-12-15

## Risks

- Data migration from the legacy tool may slip the MVP. Owner: alex.kim. Mitigation: dual-run the old and new flows for two weeks with a manual CSV fallback.
- Self-serve flow may not cover complex enterprise setups. Owner: priya.n. Mitigation: route detected enterprise accounts to assisted onboarding automatically.

## Approval

Approved by the sponsor (jordan.lee) on merge of this charter, contingent on
the security review passing (tracked in reviews/security-aurora.md).
