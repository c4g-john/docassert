# Security Policy

## Reporting a vulnerability

Email **john@c4genterprises.com** with the details. Please do not open a public
issue for a security problem.

Include what you found, how to reproduce it, and the impact you expect. A proof
of concept helps but is not required.

You can expect an acknowledgement within a few business days. There is no bug
bounty; this is a small open-source project maintained by C4G Enterprises Inc.

## Scope

`docassert` runs locally and in CI. It reads Markdown documents, validates them,
and (only when `ANTHROPIC_API_KEY` is set) sends graded excerpts to the
Anthropic API. It never executes document content and never writes outside the
paths you pass it. Reports about those boundaries, about the packaged config, or
about the GitHub Action are all in scope.

## Supported versions

Fixes land on the latest released version on PyPI. Please upgrade before
reporting, in case the issue is already resolved.
