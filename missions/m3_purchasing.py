"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    # --- Extension 5: Carbon-aware Scheduling for Interruptible Jobs ---
    from finops.sustainability import REGION_CARBON, REGION_PRICE_KWH
    gpu_watts_map = {"H100": 700, "A100": 400, "A10G": 300, "L4": 72}
    carbon_table = []
    total_base_kg = total_opt_kg = 0.0
    for j in jobs:
        if bool(int(num(j["interruptible"]))):
            gtype = j["gpu_type"]
            ngpu = int(num(j["num_gpus"]))
            hpd = num(j["hours_per_day"])
            days = num(j["days"])
            total_h = hpd * days * ngpu
            kwh = (total_h * gpu_watts_map.get(gtype, 400)) / 1000.0
            kg_base = (kwh * REGION_CARBON["us-east-1"]) / 1000.0
            kg_opt = (kwh * REGION_CARBON["europe-north1"]) / 1000.0
            total_base_kg += kg_base
            total_opt_kg += kg_opt
            carbon_table.append({
                "job_id": j["job_id"], "gpu": gtype, "kwh": round(kwh, 1),
                "us_east_kg": round(kg_base, 1), "eu_north_kg": round(kg_opt, 1),
                "saved_kg": round(kg_base - kg_opt, 1)
            })
    carbon_saved_pct = (1.0 - total_opt_kg / total_base_kg) * 100.0 if total_base_kg else 0.0

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

        print("\n-- [Your Turn Extension 5] Carbon-Aware Scheduling (Interruptible Jobs) --")
        print(f"{'job':18}{'gpu':7}{'kWh':>8}{'us-east-1(kg)':>15}{'europe-n1(kg)':>15}{'saved(kg)':>12}")
        for c in carbon_table:
            print(f"{c['job_id']:18}{c['gpu']:7}{c['kwh']:>8.1f}{c['us_east_kg']:>15.1f}{c['eu_north_kg']:>15.1f}{c['saved_kg']:>12.1f}")
        print(f"Total Carbon: {total_base_kg:,.1f} kg -> {total_opt_kg:,.1f} kg CO2e ({carbon_saved_pct:.1f}% carbon reduction, saving {total_base_kg - total_opt_kg:,.1f} kg CO2e)")

    return {
        "recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
        "extension_carbon_saved_kg": round(total_base_kg - total_opt_kg, 1),
        "extension_carbon_reduction_pct": round(carbon_saved_pct, 1),
    }


if __name__ == "__main__":
    run()
