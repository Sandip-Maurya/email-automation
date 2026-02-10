"""Tests for agent registry: config loading, merging, caching, fail-fast."""

import os
import sys
from pathlib import Path
from unittest import TestCase, main

# Allow importing src when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAgentRegistry(TestCase):
    """Tests for agent registry config loading, merging, caching, fail-fast."""

    def test_fail_fast_missing_config(self):
        """When agents config file is missing, registry raises FileNotFoundError."""
        import src.agents.registry as reg

        reg._config = None
        reg._agent_cache = {}
        orig = os.environ.get("AGENTS_CONFIG_PATH")
        try:
            os.environ["AGENTS_CONFIG_PATH"] = str(Path("/nonexistent/agents.yaml"))
            with self.assertRaises(FileNotFoundError) as ctx:
                reg._load_config()
            self.assertIn("not found", str(ctx.exception).lower())
        finally:
            if orig is not None:
                os.environ["AGENTS_CONFIG_PATH"] = orig
            else:
                os.environ.pop("AGENTS_CONFIG_PATH", None)
            reg._config = None

    def test_load_config_returns_structure(self):
        """get_all_config returns dict with defaults, agents, scenarios."""
        from src.agents.registry import get_all_config

        config = get_all_config()
        self.assertIsInstance(config, dict)
        self.assertIn("defaults", config)
        self.assertIn("agents", config)
        self.assertIn("scenarios", config)
        self.assertIn("A0_decision", config["agents"])
        self.assertIn("S1", config["scenarios"])

    def test_get_agent_config_merges_defaults(self):
        """get_agent_config merges defaults with per-agent overrides."""
        from src.agents.registry import get_agent_config

        cfg = get_agent_config("A0_decision")
        self.assertIn("system_prompt", cfg)
        self.assertIn("model", cfg)
        self.assertEqual(cfg["model"], "openai:gpt-4o-mini")
        self.assertIn("retries", cfg)

    def test_get_scenario_config(self):
        """get_scenario_config returns expected keys for S1."""
        from src.agents.registry import get_scenario_config

        s1 = get_scenario_config("S1")
        self.assertEqual(s1["name"], "Product Supply")
        self.assertEqual(s1["input_agent"], "A1_supply_extract")
        self.assertEqual(s1["trigger"], "inventory_api")
        self.assertEqual(s1["draft_agent"], "A6_draft")
        self.assertEqual(s1.get("low_confidence_threshold"), 0.5)
        s2 = get_scenario_config("S2")
        self.assertEqual(s2["draft_agent"], "A7_draft")
        s3 = get_scenario_config("S3")
        self.assertEqual(s3["draft_agent"], "A8_draft")
        s4 = get_scenario_config("S4")
        self.assertEqual(s4["draft_agent"], "A9_draft")

    def test_get_scenario_config_unknown_raises(self):
        """get_scenario_config raises ValueError for unknown scenario."""
        from src.agents.registry import get_scenario_config

        with self.assertRaises(ValueError) as ctx:
            get_scenario_config("S99")
        self.assertIn("Unknown scenario", str(ctx.exception))

    def test_get_user_prompt_template(self):
        """get_user_prompt_template returns string for draft agents, None for A0_decision."""
        from src.agents.registry import get_user_prompt_template

        for draft_id in ("A6_draft", "A7_draft", "A8_draft", "A9_draft"):
            tpl = get_user_prompt_template(draft_id)
            self.assertIsNotNone(tpl, f"{draft_id} should have template")
            self.assertIn("original_subject", tpl)
            self.assertIn("trigger_data", tpl)

        tpl0 = get_user_prompt_template("A0_decision")
        self.assertIsNone(tpl0)

    def test_get_agent_caches(self):
        """get_agent returns same cached agent for same agent_id."""
        from src.agents.registry import get_agent
        from src.models.outputs import ScenarioDecision

        agent1 = get_agent("A0_decision", ScenarioDecision)
        agent2 = get_agent("A0_decision", ScenarioDecision)
        self.assertIs(agent1, agent2)

    def test_reload_config_clears_cache(self):
        """reload_config clears in-memory config and agent cache."""
        from src.agents.registry import get_agent, get_agent_config, reload_config
        from src.models.outputs import ScenarioDecision

        get_agent("A0_decision", ScenarioDecision)
        config_before = get_agent_config("A0_decision")
        reload_config()
        config_after = get_agent_config("A0_decision")
        self.assertEqual(config_before["system_prompt"], config_after["system_prompt"])
        agent_after = get_agent("A0_decision", ScenarioDecision)
        self.assertIsNotNone(agent_after)


if __name__ == "__main__":
    main()
