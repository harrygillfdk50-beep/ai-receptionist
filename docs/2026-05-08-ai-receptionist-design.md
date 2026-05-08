# AI Receptionist — Design Specification

**Date:** 2026-05-08
**Status:** Draft — pending user review

---

## 1. Overview

A multi-tenant SaaS product that gives any business its own AI-powered receptionist. The receptionist answers phone calls AND chats on the business's website, books appointments into Google Calendar, transfers to a human when needed, takes messages, and sends SMS/email follow-ups.

Each business signs up, configures their receptionist (services, hours, FAQs, voice tone), connects their Google Calendar, gets a dedicated phone number, and embeds a chat widget on their site.

---

## 2. Goals & Non-Goals

### Goals
- Handle inbound phone calls with natural-sounding AI voice
- Handle chat conversations on a business's website (embeddable widget)
- Book / cancel / reschedule Google Calendar appointments
- Transfer phone calls to a human when AI cannot help
- Take messages and notify business owner via SMS/email
- Send follow-up SMS or email after a call
- Multi-tenant: one platform serves many businesses, each with their own config
- Self-serve onboarding via a Next.js dashboard
- Optional agency model: agency manages multiple business accounts

### Non-Goals (v1)
- Outbound sales calls (only inbound)
- Payment processing or quote generation
- Multi-language support beyond English (added later)
- Native mobile app (web dashboard only)
- Voice cloning of the business owner's voice (use ElevenLabs preset voices)

---

## 3. Success Criteria

- A business can sign up and have a working AI receptionist (phone + chat) in under 15 minutes
- AI books an appointment correctly in 90%+ of booking attempts
- AI correctly identifies when to transfer to human in 95%+ of edge cases
- Phone call latency: under 1.5 seconds from caller speaking to AI replying
- Platform supports 100+ concurrent businesses without architectural changes

---

## 4. Architecture

### 4.1 Three-Layer Pattern

This product follows the same 3-layer architecture as the parent `Automations` repo:

- **Directives (Layer 1):** Markdown SOPs in `ai-receptionist/directives/` — describe HOW the AI should behave per business type, conversation patterns, escalation rules
- **Orchestration (Layer 2):** Claude API as the conversation brain — decides intent, picks tools, handles flow
- **Execution (Layer 3):** Deterministic Python scripts in `ai-receptionist/execution/` — booking, SMS, email, transcript storage, etc.

### 4.2 System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Customer (Caller / Chatter)          │
└────────────┬────────────────────────────────┬───────────┘
             │ Phone Call                     │ Chat
             ▼                                ▼
       ┌──────────┐                    ┌────────────┐
       │  Twilio  │                    │ Chat Widget│
       │  (PSTN)  │                    │  (JS embed)│
       └─────┬────┘                    └─────┬──────┘
             │ webhook                        │ websocket
             ▼                                ▼
       ┌─────────────────────────────────────────────┐
       │         FastAPI Backend (Modal)              │
       │  ┌────────────────────────────────────────┐  │
       │  │  Conversation Engine (Claude API)      │  │
       │  │  - System prompt per business          │  │
       │  │  - Intent detection                    │  │
       │  │  - Tool calling                        │  │
       │  └────────────────────────────────────────┘  │
       │  ┌────────────────────────────────────────┐  │
       │  │  Tool Layer (Python scripts)           │  │
       │  │  - book_appointment.py                 │  │
       │  │  - transfer_call.py                    │  │
       │  │  - send_sms.py                         │  │
       │  │  - send_email.py                       │  │
       │  │  - take_message.py                     │  │
       │  └────────────────────────────────────────┘  │
       └─────────────────────────────────────────────┘
             │                                │
             ▼                                ▼
       ┌──────────────┐               ┌──────────────┐
       │  ElevenLabs  │               │  Supabase    │
       │  (TTS Voice) │               │  - Postgres  │
       └──────────────┘               │  - Auth      │
                                      │  - Storage   │
                                      └──────────────┘
             │                                │
             ▼                                ▼
       ┌──────────────┐               ┌──────────────┐
       │ Google Cal   │               │  Twilio SMS  │
       │ (Booking)    │               │  + SendGrid  │
       └──────────────┘               └──────────────┘
```

### 4.3 Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Backend | FastAPI on Modal | API server, websockets, webhooks |
| Database | Supabase (Postgres) | Multi-tenant data, auth |
| AI Brain | Claude API (Sonnet 4.5) | Conversation, intent, tool calling |
| Phone | Twilio Voice | PSTN, call routing, STT |
| Voice | ElevenLabs | Text-to-speech |
| Booking | Google Calendar API | Per-business OAuth |
| Messaging | Twilio SMS + SendGrid | Follow-ups, owner alerts |
| Dashboard | Next.js on Vercel | Business config UI |
| Widget | Vanilla JS embed | Chat on customer websites |

---

## 5. Core Flows

### 5.1 Phone Call Flow

```
1. Caller dials business's Twilio number
2. Twilio sends webhook to FastAPI: /voice/incoming
3. FastAPI loads business config from Supabase (system prompt, tools, hours)
4. Twilio streams caller audio → STT → text
5. Text sent to Claude API with system prompt + conversation history
6. Claude returns either:
   - A reply text (sent to ElevenLabs → audio → played to caller)
   - A tool call (book_appointment, transfer_call, take_message, etc.)
7. Loop until call ends or transfer triggered
8. Full transcript stored in Supabase
```

### 5.2 Chat Flow

```
1. Visitor opens chat widget on business website
2. Widget connects via WebSocket to FastAPI: /chat/ws
3. Same Claude conversation engine as phone (shared logic)
4. Messages stream back and forth
5. Same tool calling capability (book, message, follow-up)
6. Transcript stored in Supabase
```

### 5.3 Booking Flow (called as a tool)

```
1. Claude detects booking intent ("I want to book Tuesday at 2pm")
2. Claude calls tool: book_appointment(business_id, customer_name, datetime, service)
3. Python script:
   a. Fetches business's Google Calendar OAuth token from Supabase
   b. Checks slot availability via Google Calendar API
   c. If available: creates event, adds customer email, sends invite
   d. If not: returns alternative slots to Claude
4. Claude confirms with customer
5. Optional: triggers SMS/email confirmation tool
```

### 5.4 Human Handoff Flow

```
1. Claude detects: explicit request OR low confidence OR escalation keyword
2. Claude calls tool: transfer_call(business_id, reason)
3. Python script:
   a. Looks up business owner's phone from Supabase
   b. Tells Twilio to transfer call (TwiML <Dial>)
   c. Sends SMS to owner: "AI transferred call from [caller]. Reason: [X]"
4. If outside business hours: take message instead, email owner
```

### 5.5 Onboarding Flow (Dashboard)

```
1. Business signs up via Supabase Auth
2. Wizard collects:
   - Business name, type, services list
   - Operating hours (per day)
   - FAQs (free-text, parsed into knowledge base)
   - Tone preference (friendly / professional / casual)
   - Owner phone number (for transfers + alerts)
3. Connect Google Calendar (OAuth)
4. Provision Twilio phone number (via Twilio API)
5. Generate embed snippet for chat widget
6. AI receptionist live
```

---

## 6. Data Model (Supabase)

### Tables

**businesses**
- id, name, type, owner_email, owner_phone
- twilio_phone_number, google_cal_token (encrypted), google_cal_id
- system_prompt (generated from config)
- tone, hours (JSON), services (JSON), faqs (JSON)
- created_at, plan, status

**users**
- Standard Supabase auth + business_id (FK)
- role: owner / agency_admin / staff

**conversations**
- id, business_id, channel (phone/chat), caller_id, started_at, ended_at
- transcript (JSON), summary, outcome (booked/transferred/message/answered)

**appointments**
- id, business_id, conversation_id, customer_name, customer_phone, customer_email
- datetime, service, google_event_id, status

**messages_taken**
- id, business_id, conversation_id, caller_name, caller_phone, content, notified_at

**agencies** (for agency model)
- id, name, owner_email
- businesses: many-to-many to businesses table

---

## 7. The Conversation Engine

### 7.1 System Prompt Template

Each business has a generated system prompt that looks like:

```
You are the AI receptionist for {business_name}, a {business_type}.

Hours: {hours}
Services: {services}
Tone: {tone}

Knowledge Base (FAQs):
{faqs}

You have these tools available:
- book_appointment: When customer wants to schedule
- transfer_call: When customer asks for human OR you cannot help
- take_message: When transfer fails or business is closed
- send_sms_followup: To send confirmation/info after call

Rules:
- Never make up information not in FAQs
- If unsure, transfer to human
- Confirm details (date, name, service) before booking
- Keep responses under 2 sentences for phone calls
```

### 7.2 Tool Calling

Claude's tool use API handles the orchestration. Each tool is a Python function in `execution/`. Claude decides which to call and when.

---

## 8. Security & Privacy

- All API keys stored in Modal Secrets, never in code
- Google Calendar tokens encrypted at rest in Supabase
- Phone call recordings: optional, business-controlled toggle
- Transcripts retained 90 days by default, configurable
- GDPR-compliant data deletion endpoint
- Each business's data isolated via Supabase Row Level Security (RLS)

---

## 9. Phased Build Plan

| Phase | Deliverable | Time |
|---|---|---|
| 1 | Phone call MVP (Twilio + ElevenLabs + Claude, single business hardcoded) | Week 1–2 |
| 2 | Chat widget + shared AI brain | Week 2–3 |
| 3 | Google Calendar booking + tool calling | Week 3 |
| 4 | Human transfer + SMS/email follow-ups | Week 3–4 |
| 5 | Multi-tenant backend (Supabase + business config) | Week 4–5 |
| 6 | Next.js dashboard + onboarding wizard | Week 5–6 |
| 7 | Stripe billing + agency model | Week 6–7 |

---

## 10. Cost Model

### Infrastructure (your costs)

| Item | Status | Cost |
|---|---|---|
| Twilio (phone numbers + minutes) | Already subscribed | $1.15/number + $0.013/min |
| ElevenLabs (TTS) | Already subscribed | Existing plan |
| Claude API | Already subscribed | ~$5–50/month |
| Supabase | Already subscribed | Existing plan |
| Modal (hosting) | New | $5–20/month |
| Vercel (dashboard) | New | Free tier |
| SendGrid (email) | New | Free tier (100/day) |

**Net additional monthly cost: $5–20** (just Modal hosting).

### Revenue (what you charge)

Typical AI receptionist SaaS pricing: $49–299/month per business.
- 10 businesses × $99 = $990/month
- 50 businesses × $99 = $4,950/month
- 100 businesses × $99 = $9,900/month

---

## 11. Risks & Open Questions

- **Twilio call latency**: streaming STT + Claude + ElevenLabs needs < 1.5s end-to-end. Will require careful streaming implementation.
- **Voice naturalness**: ElevenLabs voices need to be tested on actual phone calls (different from web playback).
- **Google Calendar OAuth**: each business needs to authorize. Refresh token handling must be solid.
- **Twilio phone number compliance**: may need A2P 10DLC registration for SMS in the US.
- **Multi-language**: English only at v1. Spanish/other languages = phase 8+.

---

## 12. Folder Structure

```
ai-receptionist/
├── docs/
│   └── 2026-05-08-ai-receptionist-design.md   ← this file
├── directives/
│   ├── handle_phone_call.md
│   ├── handle_chat.md
│   ├── book_appointment.md
│   └── transfer_to_human.md
├── execution/
│   ├── twilio_voice_handler.py
│   ├── elevenlabs_tts.py
│   ├── claude_conversation.py
│   ├── book_appointment.py
│   ├── transfer_call.py
│   ├── send_sms.py
│   ├── send_email.py
│   └── tools_registry.py
├── dashboard/                                  ← Next.js app
│   ├── app/
│   ├── components/
│   └── lib/
├── widget/                                     ← embeddable JS
│   └── chat-widget.js
├── modal_app.py                                ← FastAPI on Modal
└── .env.example
```

---

## End of Spec
