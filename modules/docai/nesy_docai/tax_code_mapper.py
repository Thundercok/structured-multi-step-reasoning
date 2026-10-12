"""Vietnamese GTGT (VAT) tax rate to tax code mapping per Thông tư 219/2013/TT-BTC."""
from typing import Optional

TAX_RATE_TO_CODE = {
    0.0: '0',
    5.0: '5',
    8.0: '8',
    10.0: '10'
}

TAX_CODE_TO_RATE = {
    '0': 0.0,
    '5': 5.0,
    '8': 8.0,
    '10': 10.0
}

def infer_tax_code(tax_rate_percent: Optional[float] = None, subtotal: Optional[int] = None, tax_amount: Optional[int] = None) -> str:
    if tax_rate_percent is not None:
        return TAX_RATE_TO_CODE.get(float(tax_rate_percent), 'UNKNOWN')
    
    if subtotal is not None and tax_amount is not None:
        if subtotal <= 0 or tax_amount < 0:
            return 'UNKNOWN'
        
        calculated_rate = round((tax_amount / subtotal) * 100)
        return TAX_RATE_TO_CODE.get(float(calculated_rate), 'UNKNOWN')
    
    return 'UNKNOWN'

def format_tax_rate(tax_code: str) -> str:
    rate = TAX_CODE_TO_RATE.get(tax_code)
    if rate is not None:
        return f"{int(rate)}%" if rate.is_integer() else f"{rate}%"
    return 'N/A'
