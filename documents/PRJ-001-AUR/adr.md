---
kind: adr
id: AUR-adr
project: PRJ-001-AUR
title: Customer Onboarding — Architecture Decisions
owner: alex.kim
status: approved
---

## Overview

Architecture decisions for the self-serve onboarding flow. Each decision links
to the requirement it affects.

## Decisions

- **AUR-ADR-001** (affects: AUR-FR-101): Server-side validation for onboarding. Status: accepted. Context: client-only checks can be bypassed, risking invalid accounts. Decision: validate all required fields server-side before account creation. Consequences: marginally higher latency; materially stronger data integrity.
- **AUR-ADR-002** (affects: AUR-NFR-05): Queued delivery for progress emails. Status: accepted. Context: sending inline risks blocking the request path and breaching the 5-minute target. Decision: enqueue progress emails and send asynchronously. Consequences: sub-5-minute delivery is achievable; adds a queue dependency to operate.
