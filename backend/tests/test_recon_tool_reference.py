"""
Vajra "Show Underlying Tool" reference (Section 41).

The per-stage toolchain breakdown: the project's real target is
substituted into every command, external tools reflect their config, and
the active/passive split is honest.
"""
from app.projects.models import Project
from app.recon.tool_reference import build_tool_reference


def _ref(**overrides):
    defaults = dict(name="P", target="acme.com", rate_limit_rps=2.0)
    defaults.update(overrides)
    return build_tool_reference(Project(**defaults))


def test_reference_covers_the_recon_pipeline_stages():
    ref = _ref()
    keys = [stage["key"] for stage in ref["stages"]]
    assert keys == [
        "subdomain_discovery",
        "dns_resolution",
        "live_host_probing",
        "technology_detection",
        "metadata_discovery",
        "crawling",
    ]


def test_only_target_contacting_stages_are_marked_active():
    ref = _ref()
    active = {stage["key"] for stage in ref["stages"] if stage["active"]}
    assert active == {"live_host_probing", "metadata_discovery", "crawling"}
    assert not any(stage["active"] for stage in ref["stages"] if stage["key"] == "subdomain_discovery")


def test_commands_use_the_real_target_and_rate_limit():
    ref = _ref(target="shop.example", rate_limit_rps=5.0)
    all_commands = " ".join(
        tool["command"] for stage in ref["stages"] for tool in stage["tools"]
    )
    assert "shop.example" in all_commands
    assert "subfinder -d shop.example -silent -json" in all_commands
    assert "-rate-limit 5" in all_commands  # httpx inherits the project rate


def test_disabled_external_tool_is_reported_as_disabled(monkeypatch):
    monkeypatch.setattr("app.recon.tool_reference.settings.subfinder_enabled", False)
    ref = _ref()
    subfinder = next(
        tool
        for stage in ref["stages"] if stage["key"] == "subdomain_discovery"
        for tool in stage["tools"] if tool["name"].startswith("subfinder")
    )
    assert "Disabled by configuration" in subfinder["status"]


def test_every_command_is_explained_or_deliberately_bare():
    ref = _ref()
    for stage in ref["stages"]:
        for tool in stage["tools"]:
            # A tool either explains its command parts or its command is a comment.
            assert tool["command_parts"] or tool["command"].lstrip().startswith("#")
            assert tool["kind"] in {"built-in", "optional external"}
