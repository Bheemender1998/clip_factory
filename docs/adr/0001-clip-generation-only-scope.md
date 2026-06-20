# 0001 — Clip generation only (Stage 1) for the MVP

**Status:** Accepted (2026-06-19)

## Context
clip_factory targets clip-to-earn work, which spans discovery → clipping → posting →
earnings. Building all of it up front risks heavy surface before any value is proven.

## Decision
The MVP does **clip generation only**: URL in → 9:16 clips + metadata out. No campaign
discovery, no auto-posting, no earnings tracking. The human posts manually.

## Consequences
Fast to prove. Stages 2 (posting) and 3 (tracking) are gated — built only after Stage 1
value is real. See `docs/execution-plan.md`.
