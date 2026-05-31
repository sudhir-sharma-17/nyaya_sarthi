import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "Judicial AI System"
    API_V1_STR: str = "/api/v1"
    
    # LangChain / LangSmith Tracing
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_ENDPOINT: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "court_ai_judiciary")
    
    # API Keys
    HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index.bin")
    FAISS_METADATA_PATH: str = os.getenv("FAISS_METADATA_PATH", "./data/faiss_metadata.json")
    
    # Services
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./court_ai.db")
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Models
    LLM_MODEL: str = "llama3"
    HF_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.3"
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    INDIC_EMBEDDING_MODEL: str = "ai4bharat/indic-bert"

    class Config:
        case_sensitive = True

settings = Settings()
