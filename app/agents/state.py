from typing import TypedDict, Annotated, Sequence, Optional, List, Dict, Any
import operator
from langchain_core.messages import BaseMessage


class TraceStep(TypedDict):
    agent: str        
    action: str    
    output: str        
    duration_ms: int   
    metadata: Dict[str, Any]  # arbitrary extra info


class GraphState(TypedDict):
    """
    State for the multi-agent system.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    intent: str
    forced_intent: Optional[str]   # set by frontend; skips LLM routing
    context_docs: List[str]
    final_report: str
    report_suggested: bool
    suggested_title: str
    intermediate_steps: List[str]
    user_id: int

   
    working_memory: Dict[str, Any]

    
    agent_trace: Annotated[List[TraceStep], operator.add]
