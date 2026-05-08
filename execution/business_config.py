"""Hardcoded test business config for Phase 1 MVP.

In Phase 5, this will be replaced by a Supabase lookup keyed by phone number.
"""


def get_business_config() -> dict:
    return {
        "name": "Bright Smile Dental",
        "business_type": "dental clinic",
        "hours": {
            "monday": "9:00-17:00",
            "tuesday": "9:00-17:00",
            "wednesday": "9:00-17:00",
            "thursday": "9:00-19:00",
            "friday": "9:00-15:00",
            "saturday": "closed",
            "sunday": "closed",
        },
        "services": [
            "Routine cleaning",
            "Cavity filling",
            "Teeth whitening",
            "Emergency dental care",
        ],
        "faqs": [
            {"q": "Do you accept insurance?", "a": "Yes, we accept most major dental insurance plans including Delta, Cigna, and Aetna."},
            {"q": "Where are you located?", "a": "We're at 123 Main Street, Springfield."},
            {"q": "Do you treat children?", "a": "Yes, we welcome patients of all ages."},
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
"""
