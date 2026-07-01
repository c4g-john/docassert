---
kind: runbook
id: AUR-runbook
project: PRJ-001-AUR
title: Customer Onboarding — Runbook
owner: dana.okafor
status: approved
---

## Overview

Operational procedures for the self-serve onboarding service in production.

## Prerequisites

- Access to the onboarding service dashboard and the on-call PagerDuty rotation.
- Permission to restart the onboarding workers and the email queue.

## Procedures

1. Check the onboarding dashboard for error rate and queue depth.
2. If the email queue is backed up, scale the workers and confirm drain.
3. If account creation is failing, check the validation service health and logs.
4. If a customer is stuck, requeue their onboarding job from the admin console.
5. Record any manual intervention in the incident log.

## Monitoring

Watch the onboarding error rate, email delivery p95, and queue depth. Healthy is
error rate under 1%, delivery under 5 minutes, and queue depth near zero.

## Escalation

Page the on-call engineer; escalate to the delivery lead for any SEV-1 or a
sustained SEV-2.
