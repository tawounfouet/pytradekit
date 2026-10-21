# ADR-070 - Vertical Slice Delivery

## Status

Accepted for PyTradeKit 0.1.

## Decision

Milestones are delivered as coherent, testable slices that include domain behavior, qualification, architecture protection, and documentation.

## Rationale

A trading framework gains little from large layers of unfinished abstractions. Small end-to-end increments provide earlier feedback and make regressions easier to isolate.

## Consequences

- PRs remain small and cohesive where practical
- every slice carries its own tests
- architecture checks evolve with the code
- a milestone is not complete until its public behavior and packaging are qualified
