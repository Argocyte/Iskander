"""
model_lifecycle.py — Pydantic schemas for Phase 21: Democratic AI Model Lifecycle.

Defines hardware capability reporting, model metadata, and the democratic
upgrade proposal workflow. Changing the cooperative's AI "brain" is a
High-Impact action gated by hardware limits and democratic consensus.

SOVEREIGNTY & SAFETY:
  This feature prevents members from accidentally bricking the cooperative's
  server by pulling a model too large for the hardware, while ensuring the
  OS can evolve indefinitely as open-source AI improves.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class HardwareCapabilities(BaseModel):
    """System resource snapshot for model compatibility checking.

    Returned by GET /api/system/capabilities. The hardware profiler
    queries psutil and GPU telemetry to determine what the physical
    server can safely run without OOM crashes.
    """
    total_ram_gb: float = Field(..., description="Total system RAM in GiB.")
    available_ram_gb: float = Field(..., description="Currently available RAM in GiB.")
    gpu_detected: bool = Field(default=False, description="Whether a GPU was detected.")
    gpu_name: str | None = Field(default=None, description="GPU model name (e.g. 'NVIDIA RTX 4090').")
    total_vram_gb: float | None = Field(default=None, description="Total GPU VRAM in GiB.")
    available_vram_gb: float | None = Field(default=None, description="Available GPU VRAM in GiB.")
    gpu_driver: str | None = Field(default=None, description="GPU driver version string.")
    cpu_count: int = Field(..., description="Logical CPU core count.")
    max_parameters: str = Field(
        ..., description="Maximum safe model size estimate (e.g. '8B', '3B', '1B').",
    )
    quantization_recommended: str = Field(
        default="4-bit",
        description="Recommended quantization level given hardware constraints.",
    )


class ModelInfo(BaseModel):
    """Metadata for an Ollama model available on the node.

    Returned by GET /api/models/{name}/info and as part of the
    model listing endpoint.
    """
    name: str = Field(..., description="Model identifier (e.g. 'llama3.2:3b').")
    size_bytes: int = Field(default=0, description="Model file size on disk in bytes.")
    parameter_size: str = Field(default="unknown", description="Parameter count string (e.g. '3B', '7B').")
    quantization: str = Field(default="unknown", description="Quantization level (e.g. 'Q4_K_M', 'fp16').")
    family: str = Field(default="unknown", description="Model family (e.g. 'llama', 'qwen', 'olmo').")
    modified_at: str | None = Field(default=None, description="Last modified ISO timestamp.")
    digest: str | None = Field(default=None, description="Model blob digest.")


class ModelUpgradeProposal(BaseModel):
    """Request to upgrade an agent's model — requires democratic approval.

    Submitted via POST /api/models/propose_upgrade. The hardware profiler
    checks compatibility before the proposal reaches the HITL vote.
    """
    model_name: str = Field(
        ..., description="Ollama model tag to pull (e.g. 'qwen2.5:7b', 'llama3.2:3b').",
    )
    justification: str = Field(
        ..., min_length=10,
        description="Why the cooperative should adopt this model.",
    )
    target_agent_id: str | None = Field(
        default=None,
        description="If set, upgrade only this agent's model. If None, upgrade the global default.",
    )
    proposer_did: str = Field(
        ..., description="DID or address of the member proposing the upgrade.",
    )


class ModelUpgradeResult(BaseModel):
    """Response from the model upgrade proposal endpoint."""
    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal[
        "hardware_rejected",
        "pending_vote",
        "approved_pulling",
        "pull_complete",
        "pull_failed_rollback",
    ] = Field(..., description="Current state of the upgrade proposal.")
    model_name: str
    hardware_check: HardwareCapabilities | None = Field(
        default=None, description="Hardware snapshot at time of proposal.",
    )
    error: str | None = Field(default=None, description="Error message if rejected or failed.")
    previous_model: str | None = Field(
        default=None, description="Model before upgrade (for rollback reference).",
    )


class OllamaModelListResponse(BaseModel):
    """Wrapper for the list of available models on the node."""
    models: list[ModelInfo] = Field(default_factory=list)
    default_model: str = Field(..., description="Current global default model.")
