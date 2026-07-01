---
kind: qa-test-plan
id: AUR-qa-test-plan
project: PRJ-001-AUR
title: Customer Onboarding — QA / Test Plan
owner: priya.n
status: approved
---

## Scope

Functional and non-functional testing of the self-serve onboarding flow and its
progress notifications. Out of scope: billing and enterprise SSO.

## Test Approach

Automated acceptance tests mapped to each acceptance criterion, exploratory
testing of the wizard, and load testing of the notification pipeline. Every
acceptance criterion must have at least one linked test case.

## Environments

Testing runs against a staging environment seeded with anonymised production
data, plus an isolated load-test environment.

## Entry Criteria

- Every acceptance criterion has at least one test case.
- The build is deployed to staging and smoke tests pass.

## Exit Criteria

- At least 95% of test cases pass.
- No more than 0 open SEV-1 defects.
- No more than 3 open SEV-2 defects at go-live.
