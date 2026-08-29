from ghoststate.redaction import (
    VariableClass,
    classify_variable,
    is_sensitive_name,
    is_sensitive_value,
    redact_env,
)


def test_absent_variable_is_classified_absent_without_touching_value():
    decision = classify_variable("DATABASE_URL", None)
    assert decision.classification == VariableClass.ABSENT
    assert decision.sensitive is False


def test_secret_shaped_name_is_flagged_sensitive():
    for name in ["API_KEY", "STRIPE_SECRET_KEY", "DATABASE_URL", "AWS_SECRET_ACCESS_KEY", "auth_token"]:
        assert is_sensitive_name(name), f"{name} should be flagged sensitive by name"


def test_innocuous_name_is_not_flagged_by_name_alone():
    assert not is_sensitive_name("FEATURE_FLAG_LOCALE")
    assert not is_sensitive_name("APP_ENV")


def test_secret_shaped_value_is_flagged_even_with_innocuous_name():
    assert is_sensitive_value("sk_live_abcdefghijklmnopqrst")
    assert is_sensitive_value("AKIAABCDEFGHIJKLMNOP")
    assert is_sensitive_value("ghp_abcdefghijklmnopqrstuvwxyz012345")


def test_redact_env_never_returns_the_raw_value():
    env = {
        "API_KEY": "sk_live_realsecretvalue1234567890",
        "APP_ENV": "production",
        "STRIPE_SECRET_KEY": "sk_live_anothersecret1234567890",
    }
    redacted = redact_env(env)

    assert redacted == {"API_KEY": "PRESENT", "APP_ENV": "PRESENT", "STRIPE_SECRET_KEY": "PRESENT"}
    serialized = str(redacted)
    for value in env.values():
        assert value not in serialized


def test_redact_env_preserves_all_keys():
    env = {"A": "1", "B": "2", "C": "3"}
    redacted = redact_env(env)
    assert set(redacted.keys()) == set(env.keys())


def test_redact_env_is_idempotent_shaped_output():
    # calling redact twice on the same input always yields the same output
    env = {"SECRET_TOKEN": "abc", "PLAIN_VAR": "xyz"}
    assert redact_env(env) == redact_env(env)
