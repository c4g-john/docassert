---
kind: charter
id: MER-charter
project: PRJ-003-MER
title: Project Meridian — Field Service App Rollout
sponsor: priya.nair
budget:
  amount: 850000
  currency: USD
dates:
  created: 2026-03-02
  target: 2026-12-31
status: proposed
---

## Objective

Replace paper-based work orders with a mobile app for field service
technicians, cutting the administrative time per job so technicians spend more
of the day completing service work and less of it on paperwork.

## Success Criteria

- Median work-order completion time drops below 25 minutes (from 40 today).
- Paper forms per technician per week fall by at least 90%.
- Technician app-satisfaction score reaches 4.2 / 5 within 60 days of rollout.
- At least 95% of active technicians use the app for all work orders by GA.

## Scope

In scope: the field-technician mobile app, replacing paper work orders, device
rollout, and initial training. Out of scope: back-office scheduling, customer
billing, and the dispatcher console (handled separately).

## Milestones

- Kickoff — 2026-03-02
- Pilot in two regions — 2026-07-31
- App available to all technicians — 2026-12-31

## Risks

- Technicians in low-connectivity rural areas may be unable to use the app reliably. Owner: raj.patel. Mitigation: ship a full offline mode that queues work orders locally and syncs when connectivity returns.
- Rollout may slip if training takes longer than expected. Owner: priya.nair. Mitigation: run a train-the-trainer program in each region two weeks ahead of that region's cutover.

## Approval

Approved by the sponsor (priya.nair) once the offline-mode pilot passes field
testing in the two low-connectivity pilot regions.
