---
kind: prd
id: ATL-prd
project: PRJ-002-ATL
title: Partner Portal — Product Requirements
owner: raj.patel
status: proposed
---

## Overview

The modernized partner portal provides a redesigned, task-oriented UI and a
guided onboarding workflow with partner SSO.

## Product Requirements

- **ATL-PR-001** (traces: ATL-BR-001): The portal shall present each partner a task dashboard that surfaces every outstanding action in one place.
- **ATL-PR-002** (traces: ATL-BR-002): The portal shall provide a guided, self-serve onboarding workflow that requires no support ticket.

## Acceptance Criteria

- **ATL-AC-001** (verifies: ATL-PR-001): Given a partner with outstanding actions, when they open the portal, then every outstanding action is listed on the task dashboard.
- **ATL-AC-002** (verifies: ATL-PR-002): Given a new partner, when they complete the guided onboarding workflow, then an active partner account exists and no support ticket is created.
