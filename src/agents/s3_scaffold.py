"""S3 Demand IQ scaffold: placeholder steps A_D1-A_D4 (no real LLM/APIs yet)."""

from typing import Any


async def step_s3_ad1(inputs: Any) -> dict[str, Any]:
    """A_D1: Decision on what type of reply. Placeholder."""
    return {"reply_type": "allocation_summary", "source": "scaffold"}


async def step_s3_ad2(inputs: Any) -> dict[str, Any]:
    """A_D2: Input (which dashboard, report, data source). Placeholder."""
    return {
        "dashboard": "allocation",
        "report": "dcs",
        "data_source": "mock",
        "source": "scaffold",
    }


async def step_s3_ad3(inputs: Any) -> dict[str, Any]:
    """A_D3: Check Allocation. Placeholder."""
    return {"check_status": "ok", "source": "scaffold"}


async def step_s3_ad4(inputs: Any) -> dict[str, Any]:
    """A_D4: Allocation Simulation. Placeholder."""
    return {"simulated": True, "source": "scaffold"}
