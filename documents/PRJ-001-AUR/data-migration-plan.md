---
kind: data-migration-plan
id: AUR-data-migration-plan
project: PRJ-001-AUR
title: Customer Onboarding — Data Migration Plan
owner: alex.kim
status: approved
---

## Scope

Migrate active customer setup records from the legacy setup tool into the new
onboarding platform. Historical, closed records older than 24 months are out of
scope.

## Source Systems

- Legacy setup tool (MySQL 5.7), `setup` schema.
- Support export (CSV) for contact preferences.

## Field Mapping

| Source field | Target field | Transform |
|---|---|---|
| cust_name | customer.name | trim whitespace |
| signup_dt | customer.created_at | convert to ISO-8601 UTC |
| contact_pref | customer.notify_channel | map Y/N to email/none |

## Validation

- Row counts match between source and target within a 0% tolerance.
- A 5% sample is field-compared and must match exactly.

## Cutover

Freeze writes to the legacy tool, run the migration, run validation, then point
the onboarding flow at the new store.

## Rollback

If validation fails, re-point the flow at the legacy tool and discard the
partial target dataset. See the rollback plan for the full procedure.
