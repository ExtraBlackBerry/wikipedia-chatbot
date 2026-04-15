from google.adk.agents.llm_agent import Agent
from google.adk.tools import FunctionTool

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from config import QNA_AGENT_MODEL

#import tools
from .tools.qna_table import search_qna_spacy

#import prompts
from .prompt import QNA_AGENT_DESCRIPTION, QNA_AGENT_INSTRUCTION

#import logging
from orchestrator_module.util.logger import (
    before_agent_callback, before_model_callback, before_tool_callback,
    after_agent_callback, after_model_callback, after_tool_callback
)

qna_agent = Agent(
    model=QNA_AGENT_MODEL,
    name='qna_agent',
    description=QNA_AGENT_DESCRIPTION,
    instruction=QNA_AGENT_INSTRUCTION,
    tools=[
        FunctionTool(
            func=search_qna_spacy
        ),
    ],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)

