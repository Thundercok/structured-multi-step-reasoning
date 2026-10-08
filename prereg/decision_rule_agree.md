Agreement signals, offline on run11 + ae_palv2 traces (gen02_tune), exploratory. Answers canonicalized by the existing normalizer (g24 by check24 validity).
Signals: agree(PAL-v2,COT), agree(PAL-v2,ToT), n_agree over {COT,ToT,PAL-v2,SC winner}. Target: correctness of the answer that agreement would accept.
Gate (same as the logprob rule): baseline [family+level+completion_tokens] vs +signal, repeated 5-fold CV x20 grouped by group_id; delta AUROC >= 0.05 with paired-bootstrap CI lower bound > 0, in arith AND order separately. g24 report only.
Also report P(correct | agree) and every agree-and-wrong item with both answers and gold.
Policies (replay, all stages counted): G1 = PAL-v2 + COT, accept iff agree else ToT. G2 = PAL-v2; if exec fails -> ToT; else COT, accept iff agree else ToT. Versus always-ToT, W (PAL-v2 -> ToT on exec failure), always-PAL-v2: acc, tokens, escalation rate, 95% cluster-bootstrap CI.
Verdict: a working signal only if the gate passes in order; arith alone is trivial because PAL is a de-facto oracle.
