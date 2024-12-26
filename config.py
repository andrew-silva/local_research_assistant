import os
from dataclasses import dataclass


@dataclass
class Config:
    SEMANTIC_API_KEY: str = os.getenv("SEMANTIC_API_KEY", "")       # If you have a SemanticScholar API key, use it here
    OLLAMA_API_URL: str = "http://localhost:11434/api/generate"     # Default Ollama API endpoint
    OLLAMA_MODEL: str = "llama3.2"                                  # Model for Ollama
    CACHE_SIZE: int = 100                                           # Cache for API call
    DEFAULT_YEAR_FILTER: str = "2020-"                              # Default year cutoff
    PAPERS_PER_PAGE: int = 20                                       # Number of results per Semantic Scholar API Call
    MAX_PAGES: int = 1                                              # How many pages of Semantic Scholar results?
    MAX_RETRIES: int = 5                                            # Retries for SemanticScholar or Ollama calls
    TIMEOUT: int = 300                                              # Seconds until timeout for Ollama calls
    RELEVANT_PAPERS_FOR_FUTURE_WORK: int = 10                       # 10 papers used for future work ideation
