---
kind: charter
id: PHX-charter
project: PRJ-004-PHX
title: Project Phoenix — Support Response Overhaul
sponsor: dana.okafor
budget:
  amount: 500000
  currency: USD
dates:
  created: 2026-02-01
  target: 2026-11-30
status: proposed
---

## Objective

Cut first-response time on customer support tickets from a median of 9 hours to
under 1 hour by introducing tiered auto-triage and a follow-the-sun on-call
rota, so customers get a substantive first reply within the same business hour
they write in.

## Success Criteria

- Median first-response time drops below 60 minutes.
- Ticket reopen rate falls below 8%.
- Support CSAT rises above 4.3 / 5.
- At least 95% of P1 tickets receive a first response within 15 minutes.

## Scope

In scope: auto-triage classification, the on-call rota tooling, and the
response-time dashboard. Out of scope: the billing support queue and any
changes to staffing levels (handled by workforce planning).

## Milestones

- Auto-triage live in production — 2026-07-31
- Follow-the-sun rota fully staffed — 2026-11-30

## Risks

- Auto-triage may misroute edge-case tickets and slow response. Owner: sam.rivera. Mitigation: keep a human review queue for low-confidence classifications for the first 60 days.
- Follow-the-sun rota depends on hiring in the APAC region. Owner: dana.okafor. Mitigation: backfill with a contracted overflow provider until permanent hires start.

## Approval

Approved by the sponsor (dana.okafor) once the auto-triage accuracy pilot
clears 90% on the labelled test set.
