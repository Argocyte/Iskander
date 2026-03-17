"""
hardware_profiler.py — System resource detection for model compatibility (Phase 21).

Before the OS can pull a new model, it must know what the physical server
can handle. This module queries RAM via psutil and GPU VRAM via nvidia-smi
(or rocm-smi for AMD) to determine the maximum safe model size.

HARDWARE REALISM:
  The update logic rigorously checks physical system resources before
  downloading a model. A 70B parameter model will not fit on a Raspberry
  Pi with 8GB RAM — the profiler prevents the cooperative from bricking
  their server with an OOM crash.

GPU DETECTION:
  1. nvidia-smi (NVIDIA GPUs — CUDA)
  2. rocm-smi (AMD GPUs — ROCm)
  3. Fallback: CPU-only mode (no GPU detected)

MODEL SIZE HEURISTICS:
  - fp16: ~2 bytes per parameter (7B ≈ 14GB VRAM)
  - 8-bit: ~1 byte per parameter (7B ≈ 7GB)
  - 4-bit: ~0.5 bytes per parameter (7B ≈ 3.5GB)
  The profiler recommends quantization based on available memory.

GLASS BOX:
  get_capabilities() returns a HardwareCapabilities model that is logged
  as an AgentAction payload when used by the model manager.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Any

import psutil

from backend.config import settings
from backend.schemas.model_lifecycle import HardwareCapabilities

logger = logging.getLogger(__name__)

# Approximate bytes-per-parameter for each quantization level.
_BYTES_PER_PARAM = {
    "fp16": 2.0,
    "8-bit": 1.0,
    "4-bit": 0.5,
}

# Parameter count tiers (in billions) for max_parameters estimation.
_PARAM_TIERS = [0.5, 1, 3, 7, 8, 13, 14, 30, 34, 65, 70]


class HardwareProfiler:
    """
    Detects system RAM and GPU VRAM to determine model compatibility.

    Singleton: obtain via HardwareProfiler.get_instance().
    """

    _instance: "HardwareProfiler | None" = None

    @classmethod
    def get_instance(cls) -> "HardwareProfiler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_capabilities(self) -> HardwareCapabilities:
        """
        Query system resources and return a hardware capabilities snapshot.

        This is the primary entry point — called by the model manager
        before any model pull to verify the node can handle the model.
        """
        # ── RAM ────────────────────────────────────────────────────────────
        mem = psutil.virtual_memory()
        total_ram_gb = round(mem.total / (1024 ** 3), 2)
        available_ram_gb = round(mem.available / (1024 ** 3), 2)
        cpu_count = psutil.cpu_count(logical=True) or 1

        # ── GPU ────────────────────────────────────────────────────────────
        gpu_info = self._detect_gpu()

        # ── Model sizing ───────────────────────────────────────────────────
        available_memory_gb = gpu_info.get("available_vram_gb") or available_ram_gb
        safety_margin = settings.vram_safety_margin
        usable_gb = available_memory_gb * (1.0 - safety_margin)

        max_params, quant = self._estimate_max_model(usable_gb)

        return HardwareCapabilities(
            total_ram_gb=total_ram_gb,
            available_ram_gb=available_ram_gb,
            gpu_detected=gpu_info.get("detected", False),
            gpu_name=gpu_info.get("name"),
            total_vram_gb=gpu_info.get("total_vram_gb"),
            available_vram_gb=gpu_info.get("available_vram_gb"),
            gpu_driver=gpu_info.get("driver"),
            cpu_count=cpu_count,
            max_parameters=max_params,
            quantization_recommended=quant,
        )

    def can_fit_model(
        self,
        parameter_count_billions: float,
        quantization: str = "4-bit",
    ) -> tuple[bool, str]:
        """
        Check whether a model of given size fits in available memory.

        Args:
            parameter_count_billions: Model size in billions of parameters.
            quantization: Quantization level ('fp16', '8-bit', '4-bit').

        Returns:
            (fits: bool, reason: str) — whether the model fits and why/why not.
        """
        caps = self.get_capabilities()
        available_gb = caps.available_vram_gb or caps.available_ram_gb
        safety_margin = settings.vram_safety_margin
        usable_gb = available_gb * (1.0 - safety_margin)

        bytes_per_param = _BYTES_PER_PARAM.get(quantization, 0.5)
        required_gb = (parameter_count_billions * 1e9 * bytes_per_param) / (1024 ** 3)

        if required_gb <= usable_gb:
            return True, (
                f"Model ({parameter_count_billions}B @ {quantization}) requires "
                f"~{required_gb:.1f}GB; {usable_gb:.1f}GB usable. Fits."
            )
        else:
            return False, (
                f"Model ({parameter_count_billions}B @ {quantization}) requires "
                f"~{required_gb:.1f}GB but only {usable_gb:.1f}GB usable. "
                f"OOM risk — proposal rejected. Consider a smaller model or "
                f"upgrading the IskanderHearth hardware tier."
            )

    # ── GPU Detection ──────────────────────────────────────────────────────────

    def _detect_gpu(self) -> dict[str, Any]:
        """Attempt GPU detection via nvidia-smi, then rocm-smi."""
        # Try NVIDIA first.
        nvidia = self._query_nvidia_smi()
        if nvidia.get("detected"):
            return nvidia

        # Try AMD ROCm.
        rocm = self._query_rocm_smi()
        if rocm.get("detected"):
            return rocm

        logger.info("No GPU detected — running in CPU-only mode.")
        return {"detected": False}

    @staticmethod
    def _query_nvidia_smi() -> dict[str, Any]:
        """Parse nvidia-smi for GPU name, total VRAM, free VRAM, driver."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.free,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return {"detected": False}

            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                return {"detected": False}

            return {
                "detected": True,
                "name": parts[0],
                "total_vram_gb": round(float(parts[1]) / 1024, 2),
                "available_vram_gb": round(float(parts[2]) / 1024, 2),
                "driver": parts[3],
            }
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return {"detected": False}

    @staticmethod
    def _query_rocm_smi() -> dict[str, Any]:
        """Parse rocm-smi for AMD GPU VRAM."""
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--csv"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return {"detected": False}

            # rocm-smi CSV output varies; extract total and used VRAM.
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return {"detected": False}

            # Parse header + first data row.
            # Typical: "GPU,VRAM Total(B),VRAM Used(B)"
            for line in lines[1:]:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    total_bytes = float(parts[1])
                    used_bytes = float(parts[2])
                    return {
                        "detected": True,
                        "name": f"AMD GPU {parts[0]}",
                        "total_vram_gb": round(total_bytes / (1024 ** 3), 2),
                        "available_vram_gb": round((total_bytes - used_bytes) / (1024 ** 3), 2),
                        "driver": "ROCm",
                    }

            return {"detected": False}
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return {"detected": False}

    # ── Model Sizing ───────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_max_model(usable_gb: float) -> tuple[str, str]:
        """
        Estimate the maximum model size and recommended quantization.

        Returns (max_parameters_str, quantization_str).
        """
        # Try 4-bit first (most memory-efficient), then 8-bit, then fp16.
        for quant in ["4-bit", "8-bit", "fp16"]:
            bpp = _BYTES_PER_PARAM[quant]
            # Max params that fit in usable_gb.
            max_params_b = (usable_gb * (1024 ** 3)) / (bpp * 1e9)

            # Find the largest tier that fits.
            best_tier = None
            for tier in reversed(_PARAM_TIERS):
                if tier <= max_params_b:
                    best_tier = tier
                    break

            if best_tier is not None:
                return f"{best_tier}B", quant

        # Nothing fits — sub-500M territory.
        return "0.5B", "4-bit"
