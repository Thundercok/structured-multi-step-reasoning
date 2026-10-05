# Unit tests for arith_verifier and order_verifier
import pytest
from scripts.verifiers import arith_verifier, order_verifier

ARITH_WRONG_FIXTURES = [
    'Start with 11314.  \nSubtract 11147 to get 1767.  \nAdd 21566 to get 23333.  \nMultiply by 86 to get 2007558.  \nMultiply by 60 to get 120453480.  \nSubtract 50388 to get 120403092.  \nDivide by 6 to get 20067182.  \nAdd 92170 to get 20076449.  \nDivide by 4 to get 5019112.25.  \n\nAnswer: 5019112.25',
    'Start with 68716.  \nSubtract 24780: 68716 - 24780 = 43936  \nMultiply by 98: 43936 × 98 = 4305632  \nAdd 85871: 4305632 + 85871 = 4391503  \nSubtract 4324: 4391503 - 4324 = 4387179  \nAdd 44671: 4387179 + 44671 = 4431850  \nMultiply by 5: 4431850 × 5 = 22159250  \nAdd 40660: 22159250 + 40660 = 22199910  \nDivide by 9: 22199910 ÷ 9 = 2466656.666...  \n\nAnswer: 2466656.666...',
    'Start with 38705.  \nDivide by 5: 38705 / 5 = 7741  \nSubtract 2558: 7741 - 2558 = 5183  \nAdd 19951: 5183 + 19951 = 25134  \nDivide by 6: 25134 / 6 = 4189  \nMultiply by 82: 4189 * 82 = 343598  \nSubtract 32593: 343598 - 32593 = 310,005  \nMultiply by 83: 310005 * 83 = 25730415  \nAdd 37217: 25730415 + 37217 = 25767632  \n\nAnswer: 25767632',
]

ARITH_RIGHT_FIXTURES = [
    'Start with 64.  \nAdd 60: 64 + 60 = 124.  \nSubtract 9: 124 - 9 = 115.  \nAnswer: 115',
    'Start with 69.  \nMultiply by 8: 69 * 8 = 552.  \nMultiply by 5: 552 * 5 = 2760.  \nAnswer: 2760',
    'Start with 95.  \nMultiply by 7 to get 665.  \nDivide by 5 to get 133.  \nAnswer: 133',
]

ORDER_WRONG_FIXTURES = [
    ('Start by listing the runners: Dave, Grace, Heidi, Carol, Erin, Bob.\n\nFrom the clues:\n1. Dave finished before Grace.\n2. Bob finished before Erin.\n3. Erin finished after Heidi.\n4. Erin finished exactly 2 places ahead of Dave, with exactly 1 runner between them.\n\nLet’s denote the positions as 1st to 6th.\n\nFrom clue 4: Erin is 2 places ahead of Dave, with 1 runner in between. That means:\n- If Dave is in position X, Erin is in position X + 3.\n\nTry possible positions for Dave and Erin:\n- If Dave is 1st, Erin is 4th.\n- If Dave is 2nd, Erin is 5th.\n- If Dave is 3rd, Erin is 6th.\n\nTry Dave = 2nd, Erin = 5th (this fits with clue 2: Bob before Erin, so Bob must be 1st, 2nd, 3rd, or 4th).\n\nFrom clue 3: Erin finished after Heidi → Heidi must be before 5th.\n\nFrom clue 1: Dave before Grace → Grace must be after 2nd.\n\nNow assign positions:\n- Dave = 2nd\n- Erin = 5th\n- Bob must be before 5th → Bob = 1st, 3rd, or 4th\n- Heidi must be before 5th → Heidi = 1st, 3rd, or 4th\n- Grace must be after 2nd → Grace = 3rd, 4th, or 6th\n\nTry Bob = 1st, Heidi = 3rd, Grace = 4th.\n\nRemaining runners: Carol.\n\nAssign positions:\n1. Bob\n2. Dave\n3. Heidi\n4. Grace\n5. Erin\n6. Carol\n\nAnswer: Carol', {'names': ['Dave', 'Grace', 'Heidi', 'Carol', 'Erin', 'Bob'], 'clues': [['b', 0, 1, 0], ['b', 5, 4, 0], ['b', 2, 4, 0], ['g', 4, 0, 2]], 'ask': 4}),
    ('Start by listing the runners: Grace, Dave, Dave, Bob, Erin, Carol, Frank.  \nClue 1: Erin finished immediately before Grace → Erin is right before Grace.  \nClue 2: Dave finished after Erin → Dave is after Erin.  \nClue 3: Frank finished before Carol → Frank is before Carol.  \nClue 4: Carol finished exactly 2 places ahead of Erin, with exactly 1 runner between them → Carol is 3 positions ahead of Erin.  \n\nFrom Clue 4: Carol is 3 positions ahead of Erin.  \nSo if Erin is in position X, Carol is in position X - 3.  \nWith exactly one runner between them, that fits.  \n\nTry placing Erin in position 3 → Carol is in position 0 (invalid).  \nTry Erin in position 4 → Carol is in position 1.  \nTry Erin in position 5 → Carol is in position 2.  \nTry Erin in position 6 → Carol is in position 3.  \n\nTry Erin in position 4 → Carol in position 1.  \nThen Grace is in position 5 (immediately after Erin).  \nDave must be after Erin → Dave in position 6.  \nFrank must be before Carol → Frank in position 0.  \nBob is the only one left.  \n\nFinal order: Frank (1), Carol (2), Erin (3), Grace (4), Dave (5), Bob (6).  \n\nAnswer: Dave', {'names': ['Grace', 'Dave', 'Bob', 'Erin', 'Carol', 'Frank'], 'clues': [['a', 3, 0, 1], ['b', 3, 1, 0], ['b', 5, 4, 0], ['g', 4, 3, 2]], 'ask': 4}),
    ('Start by listing the runners: Carol, Bob, Erin, Grace, Alice, Frank.\n\nClue 1: Frank finished before Alice.  \nClue 2: Alice finished after Erin.  \nClue 3: Carol finished immediately before Grace.  \nClue 4: Alice finished exactly 2 places ahead of Grace, with exactly 1 runner between them.  \nClue 5: Bob finished before Carol.\n\nFrom Clue 3: Carol is immediately before Grace → Carol and Grace are consecutive, with Carol first.  \nFrom Clue 4: Alice is exactly 2 places ahead of Grace, with 1 runner between them. So if Grace is in position X, Alice is in position X + 3.  \nFrom Clue 5: Bob is before Carol.  \nFrom Clue 1: Frank is before Alice.  \nFrom Clue 2: Erin is before Alice.\n\nLet’s test possible positions for Grace.  \nIf Grace is in position 3, then Carol is in 2 (from Clue 3), and Alice is in 6 (from Clue 4).  \nThat fits with Clue 2 (Erin before Alice), Clue 1 (Frank before Alice), and Clue 5 (Bob before Carol).  \nSo the order would be:  \n1. Bob  \n2. Carol  \n3. Grace  \n4. Erin  \n5. Frank  \n6. Alice  \n\nAnswer: Alice', {'names': ['Carol', 'Bob', 'Erin', 'Grace', 'Alice', 'Frank'], 'clues': [['b', 5, 4, 0], ['b', 2, 4, 0], ['a', 0, 3, 1], ['g', 4, 3, 2], ['b', 1, 0, 0]], 'ask': 5}),
]

ORDER_RIGHT_FIXTURES = [
    ('Start by listing the runners: Carol, Grace, Alice, Heidi, Frank.\n\nFrom the clues:\n\n1. Frank finished immediately before Grace → Frank is right before Grace.\n2. Carol finished exactly 2 places ahead of Frank, with exactly 1 runner between them → Carol is two positions ahead of Frank, with one runner in between.\n3. Grace finished immediately before Heidi → Grace is right before Heidi.\n\nLet’s denote positions as 1st, 2nd, 3rd, 4th, 5th.\n\nFrom clue 3: Grace is immediately before Heidi → Grace must be in position 4, Heidi in 5.\n\nFrom clue 1: Frank is immediately before Grace → Frank must be in position 3, Grace in 4.\n\nFrom clue 2: Carol is exactly 2 places ahead of Frank, with one runner in between → Carol must be in position 1, Frank in 3.\n\nThat leaves Alice in position 2.\n\nSo the order is:\n1. Carol  \n2. Alice  \n3. Frank  \n4. Grace  \n5. Heidi  \n\nAnswer: Carol', {'names': ['Carol', 'Grace', 'Alice', 'Heidi', 'Frank'], 'clues': [['a', 4, 1, 1], ['g', 0, 4, 2], ['a', 1, 3, 1]], 'ask': 0}),
    ("Start by listing the runners: Erin, Alice, Grace, Dave, Frank.\n\nClue 1: Frank finished after Grace → Grace < Frank  \nClue 2: Erin finished immediately before Dave → Erin < Dave  \nClue 3: Erin finished exactly 2 places ahead of Frank, with exactly 1 runner between them → Erin < X < Frank, and Erin is 2 places before Frank  \nClue 4: Frank finished before Alice → Frank < Alice  \n\nFrom Clue 3, Erin must be in position 1 or 2 to have 2 places before Frank with 1 runner in between. Let's test:\n\nIf Erin is in position 1, then Frank is in position 3 (1, 2, 3).  \nIf Erin is in position 2, then Frank is in position 4 (2, 3, 4).  \nIf Erin is in position 3, then Frank is in position 5 (3, 4, 5).  \n\nTry Erin = 2, Dave = 3 (from Clue 2), Frank = 4 (from Clue 3), Alice = 5 (from Clue 4), Grace = 1 (from Clue 1).  \n\nCheck all clues:\n- Grace (1) < Frank (4) ✅  \n- Erin (2) < Dave (3) ✅  \n- Erin (2) < X (3) < Frank (4) ✅  \n- Frank (4) < Alice (5) ✅  \n\nSo the order is: Grace (1), Erin (2), Dave (3), Frank (4), Alice (5).  \n\nAnswer: Frank", {'names': ['Erin', 'Alice', 'Grace', 'Dave', 'Frank'], 'clues': [['b', 2, 4, 0], ['a', 0, 3, 1], ['g', 0, 4, 2], ['b', 4, 1, 0]], 'ask': 3}),
    ('Start by listing the runners: Alice, Bob, Grace, Erin, Carol.\n\nFrom the clues:\n1. Bob finished immediately before Grace → Bob → Grace\n2. Grace finished immediately before Alice → Grace → Alice\n3. Erin finished before Carol → Erin < Carol\n4. Grace finished after Carol → Carol < Grace\n\nFrom clues 1 and 2: Bob → Grace → Alice\n\nFrom clue 4: Carol < Grace → Carol must be before Grace\n\nFrom clue 3: Erin < Carol\n\nSo the order must include:\nErin < Carol < Grace < Alice\nAnd Bob must be immediately before Grace, so Bob must be before Grace.\n\nSo the sequence must be:\nErin < Carol < Bob < Grace < Alice\n\nThis satisfies all clues:\n- Bob immediately before Grace\n- Grace immediately before Alice\n- Erin before Carol\n- Carol before Grace\n\nThus, the 5th place is Alice.\n\nAnswer: Alice', {'names': ['Alice', 'Bob', 'Grace', 'Erin', 'Carol'], 'clues': [['a', 1, 2, 1], ['a', 2, 0, 1], ['b', 3, 4, 0], ['b', 4, 2, 0]], 'ask': 4}),
]


LATEX_WRONG_FIXTURES = [
    r"Multiply: 15 \times 4 = 65\nAnswer: 65",
    r"Divide: 100 \div 4 = 20\nAnswer: 20",
    r"Multiply: 7 \cdot 8 = 54\nAnswer: 54",
]

LATEX_RIGHT_FIXTURES = [
    r"Multiply: 15 \times 4 = 60\nDivide: 60 \div 3 = 20\nMultiply: 20 \cdot 5 = 100\nAnswer: 100",
    r"Step 1: 50 \times 2 = 100\nStep 2: 100 \div 5 = 20\nAnswer: 20",
    r"Calculation: 8 \cdot 9 = 72\nAnswer: 72",
]


@pytest.mark.parametrize("raw", ARITH_WRONG_FIXTURES + LATEX_WRONG_FIXTURES)
def test_arith_verifier_wrong_fixtures(raw: str):
    flag, reason = arith_verifier(raw)
    assert flag is True
    assert reason != "ok"


@pytest.mark.parametrize("raw", ARITH_RIGHT_FIXTURES + LATEX_RIGHT_FIXTURES)
def test_arith_verifier_right_fixtures(raw: str):
    flag, reason = arith_verifier(raw)
    assert flag is False
    assert reason == "ok"


@pytest.mark.parametrize("raw,meta", ORDER_WRONG_FIXTURES)
def test_order_verifier_wrong_fixtures(raw: str, meta: dict):
    flag, reason = order_verifier(raw, meta)
    assert flag is True
    assert reason != "ok"


@pytest.mark.parametrize("raw,meta", ORDER_RIGHT_FIXTURES)
def test_order_verifier_right_fixtures(raw: str, meta: dict):
    flag, reason = order_verifier(raw, meta)
    assert flag is False
    assert reason == "ok"
