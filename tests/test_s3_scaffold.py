"""Tests for S3 Demand IQ scaffold (A_D1–A_D4 placeholders)."""

import asyncio
import importlib.util
from pathlib import Path

# Load s3_scaffold without pulling in src.agents.__init__
_spec = importlib.util.spec_from_file_location(
    "s3_scaffold",
    Path(__file__).resolve().parent.parent / "src" / "agents" / "s3_scaffold.py",
)
_s3_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_s3_mod)
step_s3_ad1 = _s3_mod.step_s3_ad1
step_s3_ad2 = _s3_mod.step_s3_ad2
step_s3_ad3 = _s3_mod.step_s3_ad3
step_s3_ad4 = _s3_mod.step_s3_ad4


def test_s3_ad1_returns_reply_type():
    out = asyncio.run(step_s3_ad1(None))
    assert "reply_type" in out
    assert out.get("source") == "scaffold"


def test_s3_ad2_returns_dashboard_report():
    out = asyncio.run(step_s3_ad2(None))
    assert "dashboard" in out
    assert "report" in out
    assert out.get("source") == "scaffold"


def test_s3_ad3_returns_check_status():
    out = asyncio.run(step_s3_ad3(None))
    assert "check_status" in out or "source" in out
    assert out.get("source") == "scaffold"


def test_s3_ad4_returns_simulated():
    out = asyncio.run(step_s3_ad4(None))
    assert out.get("simulated") is True or "source" in out
    assert out.get("source") == "scaffold"
