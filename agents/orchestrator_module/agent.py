from google.adk.agents.llm_agent import Agent
from google.adk.tools import FunctionTool, AgentTool

from agents.orchestrator_module.prompts import ORCHESTRATOR_DESCRIPTION, ORCHESTRATOR_INSTRUCTIONS

#import tools
from agents.orchestrator_module.agent_tools.ingestion_pipeline import ingest
from agents.orchestrator_module.agent_tools.ingestion_list import list_ingested

#import agents
from agents.orchestrator_module.sub_agents.retrieval_module.agent import retrieval_agent
from agents.orchestrator_module.sub_agents.qna_module.agent import qna_agent

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import ORCHESTRATOR_AGENT_MODEL

#import logging tool
from agents.orchestrator_module.util.logger import (
    before_agent_callback, before_model_callback, before_tool_callback,
    after_agent_callback, after_model_callback, after_tool_callback,
)

root_agent = Agent(
    model=ORCHESTRATOR_AGENT_MODEL,
    name='orchestrator_agent',
    description=ORCHESTRATOR_DESCRIPTION,
    instruction=ORCHESTRATOR_INSTRUCTIONS,
    tools=[
        FunctionTool(
            func=ingest
        ),
        FunctionTool(
            func=list_ingested
        ),
        AgentTool(
            agent=retrieval_agent
        ),
        AgentTool(
            agent=qna_agent
        ),
    ],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
