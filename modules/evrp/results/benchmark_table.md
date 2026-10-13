# Comprehensive Benchmark Results: VRPTW & EVRP (PyTorch Dueling DDQN + RoutePool + Polish)

| Type | Instance | Scale ($N$) | BKS Baseline | Greedy Baseline | Beyond-ALNS DDQN+Polish | NV Gap | Fair TD Gap (%) | Time (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **VRPTW** | `Solomon_C101_VRPTW` | 100 | (10, 828.9) | (14, 2640.6) | **(13, 2446.3)** | +3 | N/A (NV Unmatched) † | 2.06s |
| **VRPTW** | `Solomon_R101_VRPTW` | 100 | (19, 1650.8) | (14, 2428.8) | **(12, 2582.0)** | -7 | INFEASIBLE (TW/SoC) 🛑 | 0.84s |
| **VRPTW** | `Solomon_RC101_VRPTW` | 100 | (15, 1619.8) | (13, 2352.9) | **(12, 2448.0)** | -3 | INFEASIBLE (TW/SoC) 🛑 | 0.85s |
| **VRPTW** | `Homberger_C1_2_1_VRPTW` | 200 | (20, 2700.0) | (24, 3856.7) | **(24, 3779.8)** | +4 | N/A (NV Unmatched) † | 1.66s |
| **VRPTW** | `Homberger_R2_4_1_VRPTW` | 400 | (4, 8920.0) | (50, 6982.7) | **(48, 7058.7)** | +44 | INFEASIBLE (TW/SoC) 🛑 | 2.12s |
| **EVRP** | `Solomon_C101_EVRP` | 100 | (10, 828.9) | (29, 5292.0) | **(12, 5671.1)** | +2 | INFEASIBLE (TW/SoC) 🛑 | 0.8s |
| **EVRP** | `Solomon_R101_EVRP` | 100 | (19, 1650.8) | (16, 4338.0) | **(11, 4890.7)** | -8 | INFEASIBLE (TW/SoC) 🛑 | 0.79s |
| **EVRP** | `Solomon_RC101_EVRP` | 100 | (15, 1619.8) | (25, 4970.9) | **(12, 5164.5)** | -3 | INFEASIBLE (TW/SoC) 🛑 | 1.07s |
| **EVRP** | `Homberger_C1_2_1_EVRP` | 200 | (20, 2700.0) | (32, 8117.0) | **(22, 7992.1)** | +2 | INFEASIBLE (TW/SoC) 🛑 | 1.41s |
| **EVRP** | `Homberger_R2_4_1_EVRP` | 400 | (4, 8920.0) | (52, 12699.9) | **(46, 13014.3)** | +42 | INFEASIBLE (TW/SoC) 🛑 | 1.85s |

> [!NOTE]
> $\dagger$ Fair TD Gap is strictly reported only when vehicle counts (NV) match BKS and solutions are verified feasible per strict project academic integrity rules.