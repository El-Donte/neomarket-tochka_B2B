from typing import Any, Optional
from pydantic import BaseModel

    
class Error(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None
