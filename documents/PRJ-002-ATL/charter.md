---
kind: charter
id: ATL-charter
project: PRJ-002-ATL
title: Atlas — Partner Portal Modernization
sponsor: mia.chen
budget:
  amount: 750000
  currency: USD
dates:
  created: 2026-02-10
  target: 2026-10-31
status: proposed
---

## Objective

Leverage our platform capabilities to drive transformational value across the
partner journey, unlock synergies between teams, and position the organization
as a best-in-class leader in partner experience going forward.

## Success Criteria

- Partner portal task-completion rate rises above 85%.
- Median partner onboarding time drops below 5 business days.
- Partner NPS increases by at least 15 points within two quarters of launch.

## Scope

In scope: the partner portal UI, the onboarding workflow, and SSO for partners.
Out of scope: partner billing and the internal admin console.

## Milestones

- Portal redesign live — 2026-07-15
- SSO and onboarding workflow complete — 2026-10-31

## Risks

- Partner SSO integration may be delayed by third-party identity providers. Owner: raj.patel. Mitigation: ship with email-based login first and layer SSO in a fast-follow release.
- Legacy portal data may not map cleanly to the new schema. Owner: mia.chen. Mitigation: run a migration dry-run against a production snapshot two weeks before cutover.

## Approval

Approved by the sponsor (mia.chen) after the security review and a partner
advisory-board preview.
