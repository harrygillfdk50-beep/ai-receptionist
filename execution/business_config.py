"""Hardcoded business config for the agency's own demo line.

This is the receptionist for OUR OWN agency — when prospects call our
demo number, they're literally experiencing the product. Every question
answered here is also a sales touchpoint.

In Phase 5, this will be replaced by a Supabase lookup keyed by phone number,
and each client gets their own row.

>>> TO CUSTOMIZE FOR YOUR AGENCY <<<
Change these fields below, then redeploy with `modal deploy modal_app.py`:
  - "name"          : your agency name
  - "owner_phone"   : your real phone (for human transfer in later phases)
  - FAQ answers     : pricing, contact info, founder name, etc.
"""


def get_business_config() -> dict:
    return {
        "name": "Aria AI Receptionists",
        "business_type": "AI receptionist service for small businesses",
        "hours": {
            "monday": "9:00-18:00",
            "tuesday": "9:00-18:00",
            "wednesday": "9:00-18:00",
            "thursday": "9:00-18:00",
            "friday": "9:00-17:00",
            "saturday": "closed",
            "sunday": "closed",
        },
        "services": [
            "24/7 AI phone receptionist for your business",
            "Automatic appointment booking into Google Calendar",
            "Website chat widget powered by the same AI",
            "Human handoff to your team when needed",
            "Custom voice, tone, and knowledge base per business",
            "SMS and email follow-ups after every call",
        ],
        "faqs": [
            {
                "q": "What does an AI receptionist actually do?",
                "a": "I answer your business's calls 24/7. I can take messages, answer common questions, book appointments into your calendar, and transfer to a real person when needed."
            },
            {
                "q": "How much does it cost?",
                "a": "Plans start at 99 dollars a month per business. Setup is a one-time 299 dollars and includes everything: a dedicated phone number, custom voice, and your business's knowledge base."
            },
            {
                "q": "How long does setup take?",
                "a": "Most businesses are live within 24 hours. We collect your hours, services, FAQs, and connect your calendar, then you're ready to take calls."
            },
            {
                "q": "Can it really book appointments?",
                "a": "Yes. I connect directly to your Google Calendar, check live availability, confirm with the caller, and send them an email invite. No double-bookings."
            },
            {
                "q": "What happens if I can't answer a question?",
                "a": "I'll transfer the call to your real phone, or take a detailed message and send it to you by text and email if you're closed."
            },
            {
                "q": "Is my customer data secure?",
                "a": "Yes. All conversations are encrypted at rest. Transcripts auto-delete after 90 days by default. We're built on enterprise infrastructure — the same kind big banks use."
            },
            {
                "q": "How is this different from a regular answering service?",
                "a": "I'm always available, never sick, never on break, and I cost less than a single hour of a human receptionist per month. I also book appointments instantly instead of taking messages."
            },
            {
                "q": "Can I try it before I commit?",
                "a": "Absolutely. You're talking to me right now — this IS the product. Want to book a 15-minute setup call to see one configured for your business?"
            },
            {
                "q": "What languages do you support?",
                "a": "Right now I speak English. Spanish and other languages are coming soon."
            },
            {
                "q": "Can I cancel anytime?",
                "a": "Yes. Month-to-month, cancel anytime. No long contracts."
            },
        ],
        "tone": "friendly",
        "owner_phone": "+15555550100",
    }


def build_system_prompt(config: dict) -> str:
    hours_lines = "\n".join(f"  {day.title()}: {h}" for day, h in config["hours"].items())
    services_lines = "\n".join(f"  - {s}" for s in config["services"])
    faqs_lines = "\n".join(f"  Q: {f['q']}\n  A: {f['a']}" for f in config["faqs"])

    return f"""You are the AI receptionist for {config['name']}, a {config['business_type']}.

Your tone is {config['tone']}.

Hours:
{hours_lines}

Services:
{services_lines}

Knowledge Base (FAQs):
{faqs_lines}

Rules:
- This is a phone call, so keep every reply SHORT and CONCISE — ideally one or two sentences.
- Never make up information not in the FAQs or services list. If unsure, say you'll have someone call them back.
- Speak naturally, like a real receptionist. Don't say "as an AI".
- Greet the caller warmly when the call starts.
- When someone seems interested in signing up, invite them to book a 15-minute setup call.
"""
