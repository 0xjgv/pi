"""Workflow stage configuration."""

from π.core.enums import Tier, WorkflowStage

# WorkflowStage → Model tier mapping
STAGE_TIERS: dict[WorkflowStage, Tier] = {
    WorkflowStage.RESEARCH: Tier.HIGH,
    WorkflowStage.DESIGN: Tier.HIGH,
    WorkflowStage.EXECUTE: Tier.HIGH,
}
