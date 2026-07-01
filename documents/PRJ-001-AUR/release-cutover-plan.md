---
kind: release-cutover-plan
id: AUR-release-cutover-plan
project: PRJ-001-AUR
title: Customer Onboarding — Release / Cutover Plan
owner: dana.okafor
status: approved
---

## Overview

Cut over from the legacy setup tool to the self-serve onboarding flow for all
new customers, in a single maintenance window.

## Pre-Cutover Checklist

- All acceptance test cases pass in staging.
- Data migration dry-run validated within tolerance.
- Rollback plan reviewed and on standby.

## Cutover Steps

1. Freeze writes to the legacy setup tool.
2. Run the data migration and its validation.
3. Point the onboarding flow at the new platform.
4. Enable the self-serve flow for new customers.
5. Run post-cutover smoke tests.

## Verification

Confirm a test customer can complete self-serve onboarding end to end and that
progress emails are delivered within the target window.

## Rollback Trigger

If smoke tests fail or onboarding error rate exceeds 5% in the first hour,
invoke the rollback plan.
