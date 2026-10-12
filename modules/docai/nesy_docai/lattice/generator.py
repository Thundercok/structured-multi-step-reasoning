"""
Candidate Lattice Generator & Combinatorial Explosion Control Module
Guarantees MAX_CANDIDATES=32 hard-capping, locale-aware parsing (VND/USD/EUR),
condition-specific confusion maps, and multi-engine ensemble fusion.
"""

from dataclasses import dataclass, field
from enum import Enum
from itertools import product as itertools_product
import re
from typing import List, Set, Dict, Any, Optional, Tuple

MAX_CANDIDATES = 32  # Hard cap — prevents Z3 nlsat blowup on dense noise


class DocCondition(Enum):
    CLEAN = "clean"
    PRINTED_NOISY = "printed_noisy"      # Standard scan artifacts
    THERMAL_FADED = "thermal_faded"      # Receipt paper degradation
    HANDWRITTEN = "handwritten"
    LOW_RES = "low_res"


class Locale(Enum):
    VND = "vn"   # 1.000.000 = 1 million (integer minor units = dong)
    USD = "us"   # 1,000,000.00 (minor units = cents)
    EUR = "eu"   # 1.000.000,00 (inverted separators, minor units = cents)


# Condition-specific confusion maps
CONFUSION_MAPS: Dict[DocCondition, Dict[str, List[str]]] = {
    DocCondition.CLEAN: {
        'O': ['0'], '0': ['O'],
        'l': ['1'], '1': ['l'],
        'S': ['5'], '5': ['S'],
        'B': ['8'], '8': ['B'],
    },
    DocCondition.PRINTED_NOISY: {
        'O': ['0', 'Q'], '0': ['O'],
        'l': ['1', 'I'], '1': ['l', 'I'],
        'S': ['5'], '5': ['S'],
        'B': ['8', '3'], '8': ['B'],
        'Z': ['2'], '2': ['Z'],
        'G': ['6'], '6': ['G'],
    },
    DocCondition.THERMAL_FADED: {
        'O': ['0', 'D'], '0': ['O', '8'],
        '8': ['0', '3', 'B'], '3': ['8'],
        '5': ['6', 'S'], '6': ['5'],
        '1': ['l', '7'], '7': ['1'],
        '4': ['9'], '9': ['4'],
    },
    DocCondition.HANDWRITTEN: {
        '1': ['7', 'l'], '7': ['1'],
        '0': ['6', 'O'], '6': ['0'],
        '4': ['9'], '9': ['4'],
        '2': ['Z'], '5': ['S'],
    },
    DocCondition.LOW_RES: {
        'O': ['0', 'Q', 'D'], '0': ['O', '8'],
        'l': ['1', 'I', '7'], '1': ['l', 'I', '7'],
        'S': ['5', '8'], '5': ['S', '6'],
        'B': ['8', '3', 'R'], '8': ['B', '0', '3'],
    },
}


@dataclass
class RawToken:
    """Single OCR/VLM extraction result before lattice expansion."""
    text: str
    word_confidence: float = 1.0                                # Overall word/line confidence
    char_confidences: List[float] = field(default_factory=list) # Per-char confidence if available
    engine: str = "unknown"                                     # 'vision_api' | 'tesseract' | 'qwen_vl' | 'pypdf'
    bbox: Optional[Tuple] = None


@dataclass
class NumericCandidate:
    raw_string: str
    parsed_value: int          # Normalized to minor units (integer)
    confidence: float          # Aggregate confidence score
    source_engine: str


@dataclass
class InvoiceFields:
    line_items: List[Dict[str, Any]]
    subtotal_cands: List[int]
    tax_cands: List[int]
    total_cands: List[int]
    discount_cands: List[int] = field(default_factory=lambda: [0])
    metadata: Dict[str, Any] = field(default_factory=dict)


def detect_locale(context_hints: Dict[str, Any]) -> Locale:
    """
    Resolves locale from document context BEFORE numeric parsing.
    context_hints: {'currency_symbol': 'đ'|'$'|'€', ...}
    """
    symbol = context_hints.get('currency_symbol', '')
    if symbol in ('đ', 'VND', '₫'):
        return Locale.VND
    if symbol == '$':
        return Locale.USD
    if symbol == '€':
        return Locale.EUR
    
    # Fallback default: VND
    return context_hints.get('fallback_locale', Locale.VND)


def _low_confidence_positions(token: RawToken, threshold: float = 0.85) -> Set[int]:
    """
    Identifies character indices flagged as low confidence.
    Handles fallback strategy for engines returning word-level confidence.
    """
    if token.char_confidences and len(token.char_confidences) == len(token.text):
        return {i for i, c in enumerate(token.char_confidences) if c < threshold}
    
    # Word-level fallback strategy:
    # If entire word confidence is below threshold, flag all ambiguous confusion characters in the word
    if token.word_confidence < threshold:
        return set(range(len(token.text)))

    return set()


def _expand_confused_chars(
    text: str,
    uncertain_positions: Set[int],
    confusion_map: Dict[str, List[str]],
) -> List[str]:
    """Generate substitution candidates ONLY at flagged low-confidence positions."""
    if not uncertain_positions:
        return [text]

    position_options: List[List[str]] = []
    for i, ch in enumerate(text):
        if i in uncertain_positions and ch in confusion_map:
            position_options.append([ch] + confusion_map[ch])
        else:
            position_options.append([ch])

    # Guard against explosion BEFORE materializing full product
    total_combinations = 1
    for opts in position_options:
        total_combinations *= len(opts)
        if total_combinations > MAX_CANDIDATES * 4:
            break

    candidates = []
    for combo in itertools_product(*position_options):
        candidates.append(''.join(combo))
        if len(candidates) >= MAX_CANDIDATES * 4:
            break

    return candidates


def _parse_numeric(raw: str, locale: Locale) -> Optional[int]:
    """Parse OCR string to integer minor units, locale-aware."""
    cleaned = re.sub(r'[^\d.,]', '', raw)  # Strip currency symbols/letters
    if not cleaned:
        return None

    if locale == Locale.VND:
        # '.' = thousands sep, no decimals expected for VND
        cleaned = cleaned.replace('.', '').replace(',', '')
    elif locale == Locale.USD:
        # ',' = thousands, '.' = decimal — convert to minor units (cents)
        cleaned = cleaned.replace(',', '')
        if '.' in cleaned:
            whole, _, frac = cleaned.partition('.')
            frac = (frac + '00')[:2]
            cleaned = whole + frac
        else:
            cleaned += '00'
    elif locale == Locale.EUR:
        # INVERTED: '.' = thousands, ',' = decimal
        cleaned = cleaned.replace('.', '')
        if ',' in cleaned:
            whole, _, frac = cleaned.partition(',')
            frac = (frac + '00')[:2]
            cleaned = whole + frac
        else:
            cleaned += '00'

    try:
        return int(cleaned)
    except ValueError:
        return None


def _rank_and_truncate(
    candidates: List[NumericCandidate],
    max_n: int = MAX_CANDIDATES,
) -> List[NumericCandidate]:
    """
    Explosion guardrail #2: cap final candidate set size.
    Ranks by confidence and dedupes by parsed_value (keeps highest-confidence variant).
    """
    best_by_value: Dict[int, NumericCandidate] = {}
    for c in candidates:
        existing = best_by_value.get(c.parsed_value)
        if existing is None or c.confidence > existing.confidence:
            best_by_value[c.parsed_value] = c

    ranked = sorted(best_by_value.values(), key=lambda c: -c.confidence)
    return ranked[:max_n]


def generate_lattice(
    token: RawToken,
    condition: DocCondition = DocCondition.PRINTED_NOISY,
    locale: Locale = Locale.VND,
) -> List[NumericCandidate]:
    """
    Main entry point: RawToken -> ranked, capped, locale-parsed candidate lattice.
    This is C(x) as referenced in the Z3 solver layer.
    """
    confusion_map = CONFUSION_MAPS[condition]
    uncertain_positions = _low_confidence_positions(token)

    string_candidates = _expand_confused_chars(
        token.text, uncertain_positions, confusion_map
    )

    numeric_candidates = []
    for s in string_candidates:
        val = _parse_numeric(s, locale)
        if val is None:
            continue
        edit_dist = sum(1 for a, b in zip(s, token.text) if a != b)
        base_conf = min(token.char_confidences) if token.char_confidences else token.word_confidence
        decayed_conf = base_conf * (0.7 ** edit_dist)
        numeric_candidates.append(NumericCandidate(
            raw_string=s,
            parsed_value=val,
            confidence=decayed_conf,
            source_engine=token.engine,
        ))

    return _rank_and_truncate(numeric_candidates)


def merge_multi_engine_lattices(
    lattices: List[List[NumericCandidate]],
) -> List[NumericCandidate]:
    """
    Ensemble fusion: when Vision API + Tesseract + Qwen-VL disagree,
    combines into one lattice, boosting confidence for cross-engine agreement.
    """
    merged: Dict[int, NumericCandidate] = {}
    for lattice in lattices:
        for cand in lattice:
            existing = merged.get(cand.parsed_value)
            if existing:
                boosted_conf = min(0.99, existing.confidence + cand.confidence * 0.3)
                merged[cand.parsed_value] = NumericCandidate(
                    raw_string=existing.raw_string,
                    parsed_value=existing.parsed_value,
                    confidence=boosted_conf,
                    source_engine=f"{existing.source_engine}+{cand.source_engine}",
                )
            else:
                merged[cand.parsed_value] = cand

    return _rank_and_truncate(list(merged.values()), max_n=MAX_CANDIDATES)


class CandidateLatticeGenerator:
    """
    High-level generator interface for backward compatibility and integration with pipeline.
    """
    def __init__(self, condition: DocCondition = DocCondition.PRINTED_NOISY, locale: Locale = Locale.VND):
        self.condition = condition
        self.locale = locale

    def generate_number_candidates(self, raw_val: Optional[Any]) -> List[int]:
        if raw_val is None:
            return []
        val_str = str(raw_val).strip()
        if not val_str:
            return []

        has_confusion_chars = any(c in val_str for c in ['O', 'o', 'l', 'I', '|', 'S', 's', 'B', 'Z', 'z'])
        conf = 0.80 if has_confusion_chars else 1.0

        token = RawToken(text=val_str, word_confidence=conf, engine="raw_input")
        lattice = generate_lattice(token, condition=self.condition, locale=self.locale)
        cands = [cand.parsed_value for cand in lattice]
        if not cands and re.sub(r'[^\d]', '', val_str):
            cands = [int(re.sub(r'[^\d]', '', val_str))]
        return cands

    def _product_filtered_amounts(self, q_cands: List[int], p_cands: List[int], a_cands: List[int]) -> List[int]:
        valid = set()
        for q in q_cands:
            for p in p_cands:
                product = q * p
                if not a_cands or product in a_cands:
                    valid.add(product)
        return sorted(list(valid)) if valid else sorted(list(a_cands))

    def build_lattice_from_raw(self, raw_data: Dict[str, Any]) -> InvoiceFields:
        locale = detect_locale({"currency_symbol": raw_data.get("currency", "VND")})

        line_items_cands = []
        for item in raw_data.get("line_items", []):
            q_cands = self.generate_number_candidates(item.get("quantity"))
            p_cands = self.generate_number_candidates(item.get("unit_price"))
            a_cands = self.generate_number_candidates(item.get("amount"))

            if not q_cands:
                q_cands = [1]
            if not p_cands:
                p_cands = [0]

            valid_a = self._product_filtered_amounts(q_cands, p_cands, a_cands)

            line_items_cands.append({
                "description": item.get("description", "Item"),
                "q_cands": q_cands,
                "p_cands": p_cands,
                "a_cands": valid_a
            })

        subtotal_cands = self.generate_number_candidates(raw_data.get("subtotal"))
        tax_cands = self.generate_number_candidates(raw_data.get("tax"))
        total_cands = self.generate_number_candidates(raw_data.get("total"))
        discount_cands = self.generate_number_candidates(raw_data.get("discount"))

        return InvoiceFields(
            line_items=line_items_cands,
            subtotal_cands=subtotal_cands or [0],
            tax_cands=tax_cands or [0],
            total_cands=total_cands or [0],
            discount_cands=discount_cands or [0],
            metadata=raw_data
        )
