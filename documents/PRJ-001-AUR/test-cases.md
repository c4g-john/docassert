---
kind: test-cases
id: AUR-test-cases
project: PRJ-001-AUR
title: Customer Onboarding — Test Cases
owner: priya.n
status: approved
---

## Overview

Test cases covering the acceptance criteria for the self-serve onboarding flow.

## Test Cases

- **AUR-TC-001** (tests: AUR-AC-001): Steps: complete the self-serve wizard with valid customer details. Expected: the account is active and zero support tickets were created.
- **AUR-TC-002** (tests: AUR-AC-002): Steps: complete an onboarding stage for an in-progress customer. Expected: a progress email is received within 5 minutes.
