import json
from pathlib import Path

from generator.generate import TelemetryGenerator


def _run_generator(output_dir: Path, seed: int = 42, nodes: int = 500) -> None:
    gen = TelemetryGenerator(seed=seed, nodes=nodes)
    gen.generate_all()
    gen.write(output_dir)


EXPECTED_FILES = [
    "campaigns.json",
    "tenants.json",
    "hosts.json",
    "emails.json",
    "files.json",
    "executions.json",
    "network.json",
    "seed_ioc.json",
]


def test_generator_deterministic(tmp_path):
    """Running with the same seed produces identical output."""
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    _run_generator(out1, seed=123, nodes=500)
    _run_generator(out2, seed=123, nodes=500)

    for fname in EXPECTED_FILES:
        f1 = out1 / fname
        f2 = out2 / fname
        assert f1.exists(), f"{fname} not created"
        assert f1.read_text() == f2.read_text(), f"{fname} differs between runs"


def test_generator_output_structure(tmp_path):
    """Generated files have correct structure."""
    _run_generator(tmp_path, seed=42, nodes=500)

    # Check seed IOC
    seed = json.loads((tmp_path / "seed_ioc.json").read_text())
    assert "sha256" in seed
    assert len(seed["sha256"]) == 64  # SHA-256 hex

    # Check campaigns
    campaigns = json.loads((tmp_path / "campaigns.json").read_text())
    assert len(campaigns) >= 3
    assert all("cluster_id" in c for c in campaigns)

    # Check hosts
    hosts = json.loads((tmp_path / "hosts.json").read_text())
    assert len(hosts) >= 50
    countries = {h["country"] for h in hosts}
    assert len(countries) >= 10  # reasonable country diversity

    # Check OS distribution
    os_counts: dict[str, int] = {}
    for h in hosts:
        os_counts[h["os_family"]] = os_counts.get(h["os_family"], 0) + 1
    assert "Windows" in os_counts

    # Check emails
    emails = json.loads((tmp_path / "emails.json").read_text())
    assert len(emails) > 0
    assert all("message_id" in e for e in emails)


def test_generator_different_seeds(tmp_path):
    """Different seeds produce different output."""
    out1 = tmp_path / "seed1"
    out2 = tmp_path / "seed2"

    _run_generator(out1, seed=1, nodes=200)
    _run_generator(out2, seed=2, nodes=200)

    hosts1 = (out1 / "hosts.json").read_text()
    hosts2 = (out2 / "hosts.json").read_text()
    assert hosts1 != hosts2, "Different seeds should produce different hosts"
