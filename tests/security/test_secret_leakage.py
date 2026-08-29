"""Adversarial tests: try to make GhostState leak a secret.

If any of these fail, that's a real vulnerability, not a style nit.
"""

from ghoststate.collectors.config import collect_configuration_metadata
from ghoststate.schema import Snapshot

REALISTIC_SECRETS = {
    "DATABASE_URL": "postgres://user:hunter2@db.internal:5432/prod",
    "STRIPE_SECRET_KEY": "sk_live_51AbCdEfGhIjKlMnOpQrStUv",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "GITHUB_TOKEN": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
    "JWT_SECRET": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "SSH_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\nMIIEow==\n-----END RSA PRIVATE KEY-----",
    "APP_NAME_HOLDING_A_KEY_ANYWAY": "sk_live_totallyunexpectedplacementxyz",
}


def test_collector_never_leaks_secret_values_into_the_snapshot():
    result = collect_configuration_metadata(REALISTIC_SECRETS)
    serialized = str(result)
    for name, value in REALISTIC_SECRETS.items():
        assert value not in serialized, f"leaked value for {name}"
    assert all(v == "PRESENT" for v in result["variables"].values())


def test_snapshot_json_export_never_contains_secret_values():
    metadata = collect_configuration_metadata(REALISTIC_SECRETS)
    snapshot = Snapshot(
        schema_version="1.0",
        execution_id="a" * 8,
        timestamp="t",
        label="",
        configuration_metadata=metadata,
    )
    exported = snapshot.to_json()
    for value in REALISTIC_SECRETS.values():
        assert value not in exported


def test_secret_shaped_value_under_an_innocuous_name_is_still_redacted():
    result = collect_configuration_metadata({"TOTALLY_FINE_VAR": "sk_live_abcdefghijklmnopqrst"})
    assert result["variables"]["TOTALLY_FINE_VAR"] == "PRESENT"
    assert "sk_live" not in str(result)
