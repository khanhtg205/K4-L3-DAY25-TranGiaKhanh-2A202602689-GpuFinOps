# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

## Technical Root Cause: The GPU-Util Lie

- `nvidia-smi` measures time-active clock duty cycle, not arithmetic throughput (FLOPs).
- Memory-bound LLM decode workloads have low arithmetic intensity (~1-2 FLOP/byte), stalling Tensor Cores while waiting for HBM transfers, causing 98% utilization with <20% MFU.
- Solution: Right-size memory-bound workloads to bandwidth/cost-efficient GPUs (e.g. A100/L4) and disaggregate prefill/decode.

## Prioritized Action Plan

1. **Purchasing Migration (Immediate, Highest ROI):** Convert 24/7 continuous inference jobs to 3-year Reserved instances and interruptible batch jobs to Spot with checkpointing ($10,040/month savings).
2. **Inference Pipeline Optimization (Month 1):** Deploy cascade routing to small models, enable prompt prefix caching, and batch background eval/search queries ($1,212/month savings).
3. **Telemetry & Governance Modernization (Month 2):** Track MFU/MBU rather than raw GPU utilization, terminate idle nodes >15m ($600/month), and enforce FOCUS chargeback.

_Figures are June-2026 as-of snapshots; re-baseline before acting._