---
kind: rollback-plan
id: AUR-rollback-plan
project: PRJ-001-AUR
title: Customer Onboarding — Rollback Plan
owner: dana.okafor
status: approved
---

## Overview

Revert the onboarding cutover, returning all new-customer setup to the legacy
tool and discarding the partial migration.

## Trigger Conditions

- Post-cutover smoke tests fail.
- Onboarding error rate exceeds 5% in the first hour.
- Data validation reports a mismatch above tolerance.

## Rollback Steps

1. Disable the self-serve onboarding flow.
2. Re-point new-customer setup at the legacy tool.
3. Discard the partial target dataset from the migration.
4. Unfreeze writes to the legacy tool.
5. Notify stakeholders and confirm the legacy path is serving.

## Verification

Confirm a test customer can be set up through the legacy tool and that no
new-customer records are being written to the target platform.
