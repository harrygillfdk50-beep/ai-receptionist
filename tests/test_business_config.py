from execution.business_config import get_business_config, build_system_prompt


def test_get_business_config_returns_required_fields():
    config = get_business_config()
    assert config["name"]
    assert config["business_type"]
    assert isinstance(config["hours"], dict)
    assert isinstance(config["services"], list)
    assert isinstance(config["faqs"], list)
    assert config["tone"] in ("friendly", "professional", "casual")


def test_build_system_prompt_includes_business_name():
    config = get_business_config()
    prompt = build_system_prompt(config)
    assert config["name"] in prompt


def test_build_system_prompt_includes_hours_and_services():
    config = get_business_config()
    prompt = build_system_prompt(config)
    for service in config["services"]:
        assert service in prompt
    assert "hours" in prompt.lower() or "open" in prompt.lower()


def test_build_system_prompt_instructs_short_replies_for_phone():
    config = get_business_config()
    prompt = build_system_prompt(config)
    assert "short" in prompt.lower() or "brief" in prompt.lower() or "concise" in prompt.lower()
