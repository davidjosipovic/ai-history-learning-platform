from pydantic import BaseModel

class ParseRequest(BaseModel):
    text: str
