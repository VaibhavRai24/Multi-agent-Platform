from typing import TypedDict, Annotated, Sequence, Optional
import operator
from langchain_core.messages import BaseMessage

class GraphState(TypedDict):
    """
    State for the multi-agent system.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    intent: str 
    forced_intent: Optional[str]  # set by frontend agent selector; skips LLM routing
    context_docs: list[str] 
    final_report: str  
    report_suggested: bool 
    suggested_title: str 
    intermediate_steps: list[str] 
    user_id: int  
