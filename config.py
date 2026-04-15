import os
from dotenv import load_dotenv
load_dotenv()

EMBED_DIM = 768
MAX_TOKENS = 512
BATCH_SIZE = 20
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
SAVE_MD = True
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

#------------------- Agent Configurations -------------------#
ORCHESTRATOR_AGENT_MODEL = 'gemini-2.5-flash-lite'
RETRIEVAL_AGENT_MODEL = 'gemini-2.5-flash-lite'
QNA_AGENT_MODEL = 'gemini-2.5-flash-lite'

#------------------- Agent API Configurations -------------------#
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

#------------------- QnA Agent Configurations -------------------#
QNA_SPACY_MODEL = "en_core_web_sm"