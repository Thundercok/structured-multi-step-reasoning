# Selected development pilot review

24 questions / 24 canonical groups; automated exact checks pass.
Human/source ownership sign-off remains pending. These are exposed development questions; no held-out gold was inspected.
Model content matches the pinned upstream revision; this preparation made no model call.
Proposed collection: DIRECT and CoT, caps 96 and 1,024 per call, seed 42; 96 conditions and at most 53,760 generated tokens.
Current DIRECT prompt is Vietnamese and CoT prompt is English. Matched caps alone do not isolate instruction from prompt-language effects.

## Human review record

Reviewer: pending
Date: pending

Confirm wording/answers/groups below; record procedural generator ownership or permission and any requested corrections.
The repository has no top-level license for this generator. Git history supports origin tracking, not a rights-holder assertion.

## 1. procedural-tuning-v1/arith_0000_en_orig

Split/family/level: train / arith / 1

A counter starts at 64. Apply these steps in order: (1) add 60; (2) subtract 9. What is the final value of the counter?

Reference: `115`
Independent solution: `115`

Proof: {"parsed_steps": 2, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 2. procedural-tuning-v1/arith_0002_en_orig

Split/family/level: calibration / arith / 1

A counter starts at 95. Apply these steps in order: (1) multiply the result by 7; (2) divide the result by 5. What is the final value of the counter?

Reference: `133`
Independent solution: `133`

Proof: {"parsed_steps": 2, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 3. procedural-tuning-v1/arith_0009_en_orig

Split/family/level: calibration / arith / 2

A counter starts at 427. Apply these steps in order: (1) multiply the result by 5; (2) subtract 635; (3) divide the result by 2; (4) subtract 386. What is the final value of the counter?

Reference: `364`
Independent solution: `364`

Proof: {"parsed_steps": 4, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 4. procedural-tuning-v1/arith_0011_en_orig

Split/family/level: train / arith / 2

A counter starts at 246. Apply these steps in order: (1) divide the result by 6; (2) subtract 5; (3) multiply the result by 6; (4) add 980. What is the final value of the counter?

Reference: `1196`
Independent solution: `1196`

Proof: {"parsed_steps": 4, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 5. procedural-tuning-v1/arith_0019_en_orig

Split/family/level: train / arith / 3

A counter starts at 2017. Apply these steps in order: (1) subtract 796; (2) add 8921; (3) subtract 3582; (4) add 7915; (5) add 5777; (6) multiply the result by 7. What is the final value of the counter?

Reference: `141764`
Independent solution: `141764`

Proof: {"parsed_steps": 6, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 6. procedural-tuning-v1/arith_0022_en_orig

Split/family/level: calibration / arith / 3

A counter starts at 5755. Apply these steps in order: (1) divide the result by 5; (2) add 5285; (3) multiply the result by 9; (4) divide the result by 3; (5) divide the result by 3; (6) subtract 2133. What is the final value of the counter?

Reference: `4303`
Independent solution: `4303`

Proof: {"parsed_steps": 6, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 7. procedural-tuning-v1/arith_0028_en_orig

Split/family/level: train / arith / 4

A counter starts at 30019. Apply these steps in order: (1) multiply the result by 83; (2) add 63095; (3) divide the result by 2; (4) multiply the result by 89; (5) subtract 11930; (6) add 68353; (7) subtract 63929; (8) add 56167. What is the final value of the counter?

Reference: `113731565`
Independent solution: `113731565`

Proof: {"parsed_steps": 8, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 8. procedural-tuning-v1/arith_0031_en_orig

Split/family/level: calibration / arith / 4

A counter starts at 56955. Apply these steps in order: (1) multiply the result by 85; (2) multiply the result by 84; (3) subtract 22117; (4) multiply the result by 68; (5) add 54342; (6) multiply the result by 23; (7) multiply the result by 39; (8) multiply the result by 37. What is the final value of the counter?

Reference: `917720389173354`
Independent solution: `917720389173354`

Proof: {"parsed_steps": 8, "independent_method": "query-derived exact arithmetic"}

Human decision: pending

## 9. procedural-tuning-v1/g24_0003_en_orig

Split/family/level: train / g24 / 1

Using each of the numbers 5, 8, 4 and 7 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `((4+7)+(5+8))`
Independent solution: `(((5+8)+4)+7)`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(((5+8)+4)+7)", "operands_from_query": [5, 8, 4, 7]}

Human decision: pending

## 10. procedural-tuning-v1/g24_0005_en_orig

Split/family/level: calibration / g24 / 1

Using each of the numbers 4, 6, 4 and 3 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `((4*3)*(6-4))`
Independent solution: `(((6-4)*4)*3)`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(((6-4)*4)*3)", "operands_from_query": [4, 6, 4, 3]}

Human decision: pending

## 11. procedural-tuning-v1/g24_0014_en_orig

Split/family/level: train / g24 / 2

Using each of the numbers 7, 2, 3 and 9 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `((3*(7+9))/2)`
Independent solution: `(((7-2)*3)+9)`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(((7-2)*3)+9)", "operands_from_query": [7, 2, 3, 9]}

Human decision: pending

## 12. procedural-tuning-v1/g24_0015_en_orig

Split/family/level: calibration / g24 / 2

Using each of the numbers 13, 2, 3 and 5 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `((13*(5-3))-2)`
Independent solution: `(((13*2)+3)-5)`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(((13*2)+3)-5)", "operands_from_query": [13, 2, 3, 5]}

Human decision: pending

## 13. procedural-tuning-v1/g24_0022_en_orig

Split/family/level: train / g24 / 3

Using each of the numbers 7, 9, 8 and 6 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `((8*6)/(9-7))`
Independent solution: `(6/((9-7)/8))`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(6/((9-7)/8))", "operands_from_query": [7, 9, 8, 6]}

Human decision: pending

## 14. procedural-tuning-v1/g24_0023_en_orig

Split/family/level: calibration / g24 / 3

Using each of the numbers 10, 4, 11 and 8 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `(8*((10+4)-11))`
Independent solution: `(((10+4)-11)*8)`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(((10+4)-11)*8)", "operands_from_query": [10, 4, 11, 8]}

Human decision: pending

## 15. procedural-tuning-v1/g24_0025_en_orig

Split/family/level: calibration / g24 / 4

Using each of the numbers 8, 13, 5 and 1 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `((5*(13-8))-1)`
Independent solution: `(((13-8)*5)-1)`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(((13-8)*5)-1)", "operands_from_query": [8, 13, 5, 1]}

Human decision: pending

## 16. procedural-tuning-v1/g24_0029_en_orig

Split/family/level: train / g24 / 4

Using each of the numbers 4, 8, 4 and 13 exactly once, together with +, -, *, / and parentheses, write an expression that equals 24.

Reference: `(4+(4*(13-8)))`
Independent solution: `(4-(4*(8-13)))`

Proof: {"exact_value": "24", "numbers_used_exactly_once": true, "independent_method": "subset dynamic programming with exact fractions", "independent_expression": "(4-(4*(8-13)))", "operands_from_query": [4, 8, 4, 13]}

Human decision: pending

## 17. procedural-tuning-v1/order_0003_en_orig

Split/family/level: train / order / 1

4 runners (Bob, Grace, Frank, Heidi) ran a race with no ties. Clues: Bob finished after Frank; Heidi finished before Frank; Grace finished immediately before Heidi. Who finished in 4th place?

Reference: `Bob`
Independent solution: `Bob`

Proof: {"consistent_orders": 1, "parsed_clues": 3, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 18. procedural-tuning-v1/order_0005_en_orig

Split/family/level: calibration / order / 1

4 runners (Grace, Carol, Dave, Heidi) ran a race with no ties. Clues: Dave finished immediately before Heidi; Grace finished immediately before Dave; Carol finished immediately before Grace. Who finished in 4th place?

Reference: `Heidi`
Independent solution: `Heidi`

Proof: {"consistent_orders": 1, "parsed_clues": 3, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 19. procedural-tuning-v1/order_0009_en_orig

Split/family/level: train / order / 2

5 runners (Erin, Heidi, Bob, Alice, Carol) ran a race with no ties. Clues: Alice finished immediately before Bob; Carol finished before Heidi; Erin finished after Bob; Heidi finished before Bob. Who finished in 4th place?

Reference: `Bob`
Independent solution: `Bob`

Proof: {"consistent_orders": 1, "parsed_clues": 4, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 20. procedural-tuning-v1/order_0010_en_orig

Split/family/level: calibration / order / 2

5 runners (Dave, Bob, Heidi, Carol, Erin) ran a race with no ties. Clues: Bob finished immediately before Heidi; Carol finished after Bob; Erin finished before Bob; Dave finished after Heidi. Who finished in 1st place?

Reference: `Erin`
Independent solution: `Erin`

Proof: {"consistent_orders": 2, "parsed_clues": 4, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 21. procedural-tuning-v1/order_0019_en_orig

Split/family/level: calibration / order / 3

6 runners (Grace, Dave, Bob, Erin, Carol, Frank) ran a race with no ties. Clues: Carol finished before Erin; Erin finished immediately before Grace; Carol finished immediately before Bob; Frank finished before Grace; Dave finished after Erin. Who finished in 5th place?

Reference: `Grace`
Independent solution: `Grace`

Proof: {"consistent_orders": 2, "parsed_clues": 5, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 22. procedural-tuning-v1/order_0022_en_orig

Split/family/level: train / order / 3

6 runners (Dave, Frank, Grace, Alice, Heidi, Bob) ran a race with no ties. Clues: Grace finished before Frank; Dave finished after Heidi; Dave finished before Alice; Dave finished immediately before Bob; Bob finished immediately before Frank. Who finished in 4th place?

Reference: `Bob`
Independent solution: `Bob`

Proof: {"consistent_orders": 2, "parsed_clues": 5, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 23. procedural-tuning-v1/order_0025_en_orig

Split/family/level: calibration / order / 4

7 runners (Bob, Carol, Alice, Erin, Grace, Frank, Dave) ran a race with no ties. Clues: Bob finished before Carol; Erin finished immediately before Carol; Bob finished immediately before Grace; Carol finished before Dave; Carol finished immediately before Alice; Alice finished before Frank. Who finished in 3rd place?

Reference: `Erin`
Independent solution: `Erin`

Proof: {"consistent_orders": 2, "parsed_clues": 6, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## 24. procedural-tuning-v1/order_0029_en_orig

Split/family/level: train / order / 4

7 runners (Erin, Heidi, Dave, Grace, Frank, Bob, Carol) ran a race with no ties. Clues: Heidi finished immediately before Grace; Erin finished immediately before Dave; Carol finished immediately before Bob; Heidi finished before Frank; Dave finished before Bob; Erin finished after Frank. Who finished in 6th place?

Reference: `Carol`
Independent solution: `Carol`

Proof: {"consistent_orders": 1, "parsed_clues": 6, "independent_method": "query-derived exhaustive ordering"}

Human decision: pending

## Model provenance

Repository: mlx-community/Qwen3-8B-4bit
Revision: `545dc4251c05440727734bcd94334791f6ab0192`

[Pinned model card](https://huggingface.co/mlx-community/Qwen3-8B-4bit/blob/545dc4251c05440727734bcd94334791f6ab0192/README.md)
All runtime model/tokenizer files are matched to upstream hashes; weights use SHA-256, ordinary files Git blob SHA-1.
