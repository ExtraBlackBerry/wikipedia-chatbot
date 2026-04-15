from google.adk.agents.llm_agent import Agent
from google.adk.tools import FunctionTool

from .prompts import RETRIEVAL_AGENT_DESCRIPTION, RETRIEVAL_AGENT_INSTRUCTION
from .pipeline.retrieval_pipeline import retrieve_simple

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))
from config import RETRIEVAL_AGENT_MODEL

#import logging
from agents.orchestrator_module.util.logger import (
    before_agent_callback, before_model_callback, before_tool_callback,
    after_agent_callback, after_model_callback, after_tool_callback
)

retrieval_agent = Agent(
    model=RETRIEVAL_AGENT_MODEL,
    name='retrieval_agent',
    description= RETRIEVAL_AGENT_DESCRIPTION,
    instruction= RETRIEVAL_AGENT_INSTRUCTION,
    tools=[
        FunctionTool(
            func=retrieve_simple
        )
    ],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
