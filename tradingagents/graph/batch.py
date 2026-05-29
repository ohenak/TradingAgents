from dataclasses import dataclass
from typing import Optional


@dataclass
class BatchTickerResult:
    """Public return type for propagate_many(). One record per ticker."""
    ticker: str
    state: Optional[dict]
    decision: Optional[str]
    error: Optional[Exception]
