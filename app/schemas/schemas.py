from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    full_name: Optional[str] = None

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Document Schemas ---
class DocumentResponse(BaseModel):
    id: int
    title: str
    document_id: str
    file_type: str
    status: str
    chunks_indexed: int
    created_at: datetime
    class Config:
        from_attributes = True

# --- Chat Schemas ---
class MessageBase(BaseModel):
    role: str # user or assistant
    content: str

class MessageCreate(MessageBase):
    pass

class ChatBase(BaseModel):
    title: str

class ChatResponse(ChatBase):
    id: int
    created_at: datetime
    messages: List[MessageBase] = []
    class Config:
        from_attributes = True

class ChatQuery(BaseModel):
    query: str
    chat_id: Optional[int] = None
    agent: Optional[str] = None  # web, rag, summary, data, report, auto

# --- Report Schemas ---
class ReportBase(BaseModel):
    title: str
    content_format: str
    content: str

class ReportResponse(ReportBase):
    id: int
    s3_url: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

# --- Agent Interaction Schemas ---
class AgentRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None
    report_suggested: Optional[bool] = False
    suggested_title: Optional[str] = ""
