from typing import Any, Optional, List
from pydantic import BaseModel, Field

class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[Any] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class ParaphraseRequest(BaseModel):
    text: str = Field(..., min_length=1)
    tone: Optional[str] = "neutral"
    
class ParaphraseResponse(BaseResponse):
    paraphrased_text: str

class GrammarRequest(BaseModel):
    text: str = Field(..., min_length=1)

class GrammarResponse(BaseResponse):
    corrected_text: str

class SimplifyRequest(BaseModel):
    text: str = Field(..., min_length=1)
    reading_level: Optional[str] = "basic"

class SimplifyResponse(BaseResponse):
    simplified_text: str

class ToneRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_tone: str = "professional"

class ToneResponse(BaseResponse):
    toned_text: str

class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    max_length: Optional[int] = 150

class SummarizeResponse(BaseResponse):
    summary: str
