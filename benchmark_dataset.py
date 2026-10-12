"""
benchmark_dataset.py — Curated Real Evaluation Dataset for Reasoning Router.
30 balanced questions across 3 clusters:
  1. PAL: Program-Aided Language (Arithmetic / Multi-step Math / Exact calculations)
  2. REACT: Tool-augmented ReAct (Chained arithmetic with observations)
  3. PLAIN: Reasoning Ladder (Transitive logic, qualitative deductions, commonsense)
"""

from typing import List, Tuple

# Format: (query, gold_standard_answer)

PAL_BENCHMARK: List[Tuple[str, str]] = [
    # GSM8K / Math calculations where code execution prevents calculation slip
    ("Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?", "72"),
    ("Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn in dollars?", "10"),
    ("Betty is saving money for a new wallet which costs $100. Betty has only half of the money she needs. Her parents give her $15, and her grandparents give her twice as much as her parents. How much more money does Betty need to buy the wallet?", "5"),
    ("Albert buys 2 large pizzas and 2 small pizzas per week for 4 weeks. A large pizza has 16 slices and a small pizza has 8 slices. In 4 weeks, how many slices of pizza does Albert eat in total?", "192"),
    ("A store offers a 20% discount on a $150 jacket. Sales tax is 8% applied to the discounted price. What is the final total price in dollars?", "129.6"),
    ("A train travels at 75 km/h for 2 hours, and then 90 km/h for 1.5 hours. What is the total distance traveled in kilometers?", "285"),
    ("If a rectangle has length 24 cm and width 18 cm, what is its perimeter in cm?", "84"),
    ("A farmer has 120 chickens and cows in total. Together they have 320 legs. How many cows are on the farm?", "40"),
    ("Compute the sum of all integers from 1 to 50 inclusive.", "1275"),
    ("A car depreciates by 10% each year. If it was bought for $20,000, what is its value after 2 years?", "16200"),
]

REACT_BENCHMARK: List[Tuple[str, str]] = [
    # Explicit calculation and intermediate state verification
    ("Calculate the arithmetic expression: (345 * 28) - (1240 / 5) + 89. Give the exact final number.", "9501"),
    ("A warehouse receives 24 crates of 18 boxes, 15 crates of 25 boxes, and 30 crates of 12 boxes. How many boxes in total were received?", "1167"),
    ("Evaluate: 15% of 840 plus 25% of 620 minus 30% of 450.", "146"),
    ("Find the result of: (78 * 14) + (96 / 8) - (45 * 3).", "969"),
    ("A trip has 3 segments: 145 km in 2 hours, 210 km in 3 hours, and 85 km in 1 hour. What is the total distance in km?", "440"),
    ("Compute the value of: (125 * 16) - (450 / 9) + (32 * 25).", "2750"),
    ("A factory produces 450 units on Monday, 520 on Tuesday, and 610 on Wednesday. If 80 defective units are discarded, how many good units remain?", "1500"),
    ("Calculate: (56 * 23) - (840 / 12) + (15 * 18).", "1488"),
    ("An investor buys 50 shares at $24 each, 30 shares at $35 each, and pays a flat fee of $15. What is the total investment in dollars?", "2265"),
    ("Evaluate: 3 * (45 + 55) - 4 * (120 - 85) + 250 / 5.", "210"),
]

PLAIN_BENCHMARK: List[Tuple[str, str]] = [
    # Logic deduction, transitive reasoning, qualitative comparison
    ("Alice is taller than Bob. Charlie is shorter than Bob. David is taller than Alice. Who is the shortest person among them?", "Charlie"),
    ("All roses are flowers. Some flowers fade quickly. Can we conclude with certainty that all roses fade quickly? Answer Yes or No.", "No"),
    ("Five runners (A, B, C, D, E) finished a race. A finished before B but behind C. D finished before C but behind E. Who finished first?", "E"),
    ("If today is Tuesday, what day of the week will it be in exactly 100 days?", "Thursday"),
    ("A box contains 5 red balls, 4 green balls, and 3 blue balls. If you draw one ball without looking, which color are you most likely to pick?", "Red"),
    ("Tom is older than Jerry. Jerry is older than Spike. Tyke is younger than Spike. Is Tom older than Tyke? Answer Yes or No.", "Yes"),
    ("If all bloops are razzies, and all razzies are giggles, are all bloops necessarily giggles? Answer Yes or No.", "Yes"),
    ("A farmer needs to cross a river with a wolf, a goat, and a cabbage. If left alone, the wolf eats the goat, and the goat eats the cabbage. Which item must the farmer take across first?", "Goat"),
    ("Mary's father has 5 daughters: Nana, Nene, Nini, Nono, and what is the fifth daughter's name?", "Mary"),
    ("Which is heavier: 1 kilogram of steel or 1 kilogram of feathers? Answer Steel, Feathers, or Equal.", "Equal"),
]


def get_curated_benchmark() -> List[Tuple[str, str]]:
    """Returns the full 30-question balanced benchmark."""
    return PAL_BENCHMARK + REACT_BENCHMARK + PLAIN_BENCHMARK


def get_train_test_split(test_ratio: float = 0.5) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Stratified 50/50 split (15 train, 15 test) across the 3 categories."""
    n_pal = len(PAL_BENCHMARK)
    n_react = len(REACT_BENCHMARK)
    n_plain = len(PLAIN_BENCHMARK)

    k_pal = int(n_pal * (1 - test_ratio))
    k_react = int(n_react * (1 - test_ratio))
    k_plain = int(n_plain * (1 - test_ratio))

    train = PAL_BENCHMARK[:k_pal] + REACT_BENCHMARK[:k_react] + PLAIN_BENCHMARK[:k_plain]
    test = PAL_BENCHMARK[k_pal:] + REACT_BENCHMARK[k_react:] + PLAIN_BENCHMARK[k_plain:]
    return train, test
