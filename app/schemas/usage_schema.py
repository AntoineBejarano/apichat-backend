from pydantic import BaseModel
from typing import List, Optional

class FunctionUsage(BaseModel):
    function_name: str
    count: int
    tokens_used: int

    model_config = {
        "from_attributes": False
    }

class UsageOut(BaseModel):
    total_tokens: int
    function_calls: List[FunctionUsage]

    model_config = {
        "from_attributes": False
    }
