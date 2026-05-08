# AI Receptionist

A multi-tenant SaaS that gives any business its own AI-powered receptionist — handles phone calls AND website chat, books appointments to Google Calendar, transfers to a human when needed, takes messages, and sends SMS/email follow-ups.

## Stack

- **Backend:** FastAPI on Modal
- **Database:** Supabase (Postgres + Auth)
- **AI Brain:** Claude API (Sonnet 4.5)
- **Phone:** Twilio Voice
- **Voice (TTS):** ElevenLabs
- **Booking:** Google Calendar API
- **Messaging:** Twilio SMS + SendGrid
- **Dashboard:** Next.js on Vercel
- **Widget:** Vanilla JS embed

## Status

Currently in design phase. See [docs/2026-05-08-ai-receptionist-design.md](docs/2026-05-08-ai-receptionist-design.md) for the full spec.

## Architecture

Follows a 3-layer pattern:

- **Directives** (`directives/`) — Markdown SOPs describing how the AI should behave
- **Orchestration** — Claude API decides intent and picks tools
- **Execution** (`execution/`) — Deterministic Python scripts for booking, SMS, transfers, etc.

## Folder Structure

```
ai-receptionist/
├── docs/             # Design specs and documentation
├── directives/       # Markdown SOPs for AI behavior
├── execution/        # Python tool scripts
├── dashboard/        # Next.js business config UI
├── widget/           # Embeddable chat widget
├── modal_app.py      # FastAPI app on Modal
└── .env.example
```

## Setup (coming soon)

Build phases:

| Phase | Deliverable |
|---|---|
| 1 | Phone call MVP (Twilio + ElevenLabs + Claude) |
| 2 | Chat widget |
| 3 | Google Calendar booking |
| 4 | Human transfer + SMS/email follow-ups |
| 5 | Multi-tenant backend (Supabase) |
| 6 | Next.js dashboard + onboarding |
| 7 | Stripe billing + agency model |
