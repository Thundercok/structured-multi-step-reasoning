# M-to-D budget interpretation and retrospective sensitivity

All tables in this review are added after inspection. No inference; original IDs, plans and per-draw artifacts verified.
Draw indices 0/1 below mean first/second draw.

| Draw | A question rescued from M to D_w0 | M cap | D_w0 cap | Completion including EOS | Finish / parse change |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | g24_0014_en_orig | 931 | 1536 | 1308 | length/fail -> stop/marker |
| 1 | g24_0014_en_orig | 931 | 1536 | 1263 | length/fail -> stop/marker |
| 1 | g24_0023_en_orig | 930 | 1536 | 982 | length/fail -> stop/marker |

F correctness is unchanged item by item between M and D_w0, not merely unchanged in total. Its stop-finished completions cannot use extra cap after EOS; the remaining length-finished cases stay wrong in the observed range.
For g24_0023 in the second draw, a valid expression already appears in the M trace but its final answer is truncated. This case measures finalization under the fixed answer contract, not failure to find any solution.
M fixes new completion allowance at L_i=2048-P_i_CONT. D_w0 allows more new tokens at these items; it does not change seed/prompt or create a new draw.
Thus part of F-A at M is timely production of a scored answer under a tighter completion window. It is not evidence of a higher unconstrained correctness ceiling or isolated correction mechanism.
Keep registered M as primary; report the weaker D contrast without selecting a favorable cap. D costs remain conditional on historical base counts/EOS scope.

| Draw | F-A wins among base-wrong | A-F wins | Net |
| --- | --- | --- | ---: |
| 0 | g24_0014_en_orig, order_0006_en_orig | arith_0039_en_orig | +1 |
| 1 | g24_0023_en_orig | none | +1 |

The first draw's net +1 is two wins minus one loss, not one uniquely identifiable rescued item. The second draw's sole win is a different G24 item.

Registered configuration in replication plan SHA-256 `132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6`:
- `/replication/analysis_spec/bootstrap_samples` = 2000
- `/replication/analysis_spec/bootstrap_seed` = 20261013

| Draw | D weight | Offset | Available cells | All-12-question contrast |
| --- | ---: | ---: | ---: | --- |
| 0 | 0 | -8 | 36/36 | descriptive, available |
| 0 | 0 | +0 | 36/36 | descriptive, available |
| 0 | 0 | +8 | 0/36 | not estimable; no extrapolation or selected subset |
| 0 | 1 | -8 | 36/36 | descriptive, available |
| 0 | 1 | +0 | 36/36 | descriptive, available |
| 0 | 1 | +8 | 36/36 | descriptive, available |
| 1 | 0 | -8 | 36/36 | descriptive, available |
| 1 | 0 | +0 | 36/36 | descriptive, available |
| 1 | 0 | +8 | 0/36 | not estimable; no extrapolation or selected subset |
| 1 | 1 | -8 | 36/36 | descriptive, available |
| 1 | 1 | +0 | 36/36 | descriptive, available |
| 1 | 1 | +8 | 36/36 | descriptive, available |

D -8 and D_w1 +8 use original new-completion IDs. D_w0 +8 exceeds the collected caps and is not estimated under the frozen replay rule, including early-stop records. This does not validate historical base EOS counts.

| Point | Contrast | Delta (pp) | Descriptive percentile CI (pp) | Added-after-inspection sign-flip p |
| --- | --- | ---: | --- | ---: |
| M | CONT-A | +20.8 | [+4.2, +37.5] | 0.125000 |
| M | F-A | +25.0 | [+4.2, +45.8] | 0.109375 |
| M | F-CONT | +4.2 | [-8.3, +16.7] | 1.000000 |
| D_w0 | CONT-A | +8.3 | [-16.8, +33.3] | 0.765625 |
| D_w0 | F-A | +12.5 | [-12.5, +33.3] | 0.507812 |
| D_w0 | F-CONT | +4.2 | [-8.3, +16.7] | 1.000000 |
| D_w1 | CONT-A | +0.0 | [-33.3, +29.2] | 1.000000 |
| D_w1 | F-A | +12.5 | [-12.5, +33.3] | 0.507812 |
| D_w1 | F-CONT | +12.5 | [-4.2, +33.3] | 0.500000 |

Bootstrap and sign-flip have different assumptions and small-sample calibration. Neither is used to establish a confirmatory GO from these inspected 12 groups.
Sign-flip enumeration assumes groupwise sign exchangeability, beyond a weak zero-mean null. No formal deployment/superiority/mechanistic/Stage 0 claim is enabled.
