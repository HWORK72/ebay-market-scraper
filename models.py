from dataclasses import dataclass, asdict
from typing import Any, Dict

@dataclass(frozen=True, slots=True)
class ProductItem:
    title: str
    price: str
    shipping: str
    condition: str
    item_url: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)