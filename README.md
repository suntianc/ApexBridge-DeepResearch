# ApexBridge Deep Research System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready intelligent deep research system powered by LangGraph, FastAPI, and multi-LLM support. This system automates the entire research workflow from search to final report generation, featuring adaptive research planning, semantic knowledge storage, and real-time streaming feedback.

## ✨ Features

### 🔄 Intelligent Research Workflow
- **Adaptive Planning**: Dynamic search query generation based on gap analysis
- **Multi-round Iteration**: Continues research until information sufficiency is achieved
- **Four-stage Pipeline**: Planner → Searcher → Analyst → Publisher

### 🧠 Advanced AI Integration
- **Multi-Model Support**: DeepSeek (V3, R1), OpenAI, Ollama, and more via LiteLLM
- **RAG Architecture**: Semantic retrieval using LanceDB vector database
- **Reasoning Engine**: DeepSeek Reasoner for complex analysis

### 🚀 Production-Ready
- **FastAPI Backend**: High-performance async API server
- **Streaming Responses**: Real-time SSE for research progress tracking
- **Modular Design**: Clean architecture with separation of concerns
- **State Management**: LangGraph checkpointing with SQLite persistence

### 📊 Knowledge Management
- **Vector Storage**: LanceDB for semantic similarity search
- **Automatic Chunking**: Intelligent document segmentation
- **Citation Tracking**: Source attribution for all information

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Research Workflow                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐ │
│  │ Planner │ -> │ Searcher │ -> │ Analyst │ -> │ Publisher│ │
│  └─────────┘    └──────────┘    └─────────┘    └──────────┘ │
│       │              │              │              │        │
│       └──────────────┴──────────────┴──────────────┘        │
│                           │                                │
│                           ↓                                │
│                  ┌─────────────────┐                       │
│                  │   Knowledge     │                       │
│                  │   Base (RAG)    │                       │
│                  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.10 or higher
- SearXNG search engine (running on port 8888)
- Ollama (optional, for local embeddings)
- API keys for:
  - DeepSeek API (recommended)
  - OpenAI API (optional)
  - Other LLM providers (optional)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone git@github.com:suntianc/ApexBridge-DeepResearch.git
cd ApexBridge-DeepResearch
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env  # If exists, otherwise create from .env template
```

Edit `.env` with your configuration:

```env
# Service Configuration
API_HOST=0.0.0.0
API_PORT=23800

# Data Storage Paths
LANCEDB_PATH=./data/lancedb
CHECKPOINT_DB_PATH=./data/checkpoints.db

# External Services
SEARXNG_BASE_URL=http://localhost:8888/search

# API Keys (Use environment variables in production!)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

⚠️ **Security Note**: Never commit `.env` files with real API keys to version control!

### 5. Set Up External Services

#### SearXNG Search Engine

**Option A: Docker (Recommended)**

```bash
docker run -d \
  --name searxng \
  -p 8888:8080 \
  -v $(pwd)/searxng:/etc/searxng \
  searxng/searxng:latest
```

**Option B: Manual Installation**

Follow the [SearXNG documentation](https://docs.searxng.org/) for manual setup.

#### Ollama (Optional, for local embeddings)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required models
ollama pull nomic-embed-text
ollama pull deepseek-r1
```

## 🚀 Usage

### Start the Server

```bash
python main.py
```

The API will be available at `http://localhost:23800`

### API Endpoints

#### Start a Research Session

**Endpoint**: `GET /api/stream?topic={your_topic}`

**Response**: Server-Sent Events (SSE) stream

**Example using curl**:

```bash
curl -N "http://localhost:23800/api/stream?topic=AI%20in%20Healthcare%202024"
```

**Example using Python**:

```python
import httpx
import sseclient

with httpx.stream("GET", "http://localhost:23800/api/stream", params={"topic": "AI in Healthcare 2024"}) as response:
    client = sseclient.SSEClient(response)
    for event in client.events():
        print(event.data)
```

#### Get Research History

**Endpoint**: `GET /api/history`

Returns a list of previous research sessions.

### Using the Client

```python
from app.api.research import graph

# Run a research session
async def run_research():
    config = {"configurable": {"thread_id": "unique-thread-id"}}
    inputs = {
        "topic": "Quantum Computing Market Analysis",
        "iteration_count": 0,
        "max_iterations": 3,
        "search_queries": [],
        "web_results": []
    }

    async for event in graph.astream(inputs, config=config):
        print(f"Step: {event}")

import asyncio
asyncio.run(run_research())
```

## 📁 Project Structure

```
ApexBridge_DeepResearch/
├── app/                          # Application core
│   ├── api/                      # API routes
│   │   ├── research.py          # Research endpoints
│   │   └── history.py           # History endpoints
│   ├── core/                     # Core utilities
│   │   ├── config.py            # Configuration management
│   │   └── llm.py               # LLM integration
│   ├── modules/                  # Feature modules
│   │   ├── knowledge/           # Knowledge management
│   │   │   ├── vector.py        # Vector database
│   │   │   └── rdb.py           # Relational DB
│   │   ├── orchestrator/        # Workflow orchestration
│   │   │   ├── graph.py         # LangGraph workflow
│   │   │   └── state.py         # State definitions
│   │   ├── perception/          # Data perception
│   │   │   ├── search.py        # Search integration
│   │   │   └── crawler.py       # Web crawling
│   │   └── insight/             # Insights & prompts
│   │       └── prompts.py       # LLM prompts
│   └── worker.py                # Background workers
├── data/                         # Data storage
│   ├── lancedb/                 # Vector database files
│   └── checkpoints.db           # LangGraph checkpoints
├── main.py                       # Application entry point
├── requirements.txt              # Dependencies
├── .env                          # Environment variables (not in repo)
├── .gitignore                    # Git ignore rules
├── LICENSE                       # MIT License
└── README.md                     # This file
```

## 🔧 Configuration

### Models

The system supports multiple LLM providers through LiteLLM:

| Provider | Model Name | Purpose |
|----------|-----------|---------|
| DeepSeek | `deepseek/deepseek-chat` | Fast generation |
| DeepSeek | `deepseek/deepseek-reasoner` | Complex reasoning |
| OpenAI | `openai/gpt-4o` | General purpose |
| Ollama | `ollama/nomic-embed-text` | Local embeddings |
| Ollama | `ollama/deepseek-r1` | Local reasoning |

### Customization

#### Modify Research Prompts

Edit `app/modules/insight/prompts.py` to customize LLM prompts:

```python
class ResearchPrompts:
    @staticmethod
    def planner_initial(topic: str) -> str:
        return f"Your custom initial planning prompt for: {topic}"

    # Add more custom prompts...
```

#### Adjust Search Parameters

Edit `app/core/config.py` or `.env`:

```python
SEARXNG_BASE_URL=http://localhost:8888/search
SEARCH_ENGINES=google,bing,duckduckgo
MAX_SEARCH_RESULTS=5
```

#### Configure Vector Database

```python
# In app/modules/knowledge/vector.py
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
VECTOR_DIMENSION=768
```

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

Run with coverage:

```bash
pytest --cov=app tests/
```

## 📊 Performance Tuning

### For Better Performance:

1. **Increase Chunk Size**: Reduce LLM calls by increasing `chunk_size` in vector.py
2. **Cache Results**: Implement Redis for query result caching
3. **Parallel Processing**: Use Celery for concurrent research tasks
4. **GPU Acceleration**: Use Ollama with CUDA for faster embeddings

### Monitoring

Add structured logging:

```python
from loguru import logger

logger.info("Research started", extra={"topic": topic, "thread_id": thread_id})
```

## 🔒 Security Considerations

1. **Never commit API keys** - Use environment variables or secret managers
2. **Validate inputs** - Sanitize user queries before processing
3. **Rate limiting** - Implement API rate limiting for production
4. **HTTPS** - Use HTTPS in production with proper certificates
5. **API Authentication** - Add authentication middleware for API access

## 🐛 Troubleshooting

### Common Issues

**Issue**: SearXNG connection fails
```bash
# Check if SearXNG is running
curl http://localhost:8888/search?q=test

# Verify SEARXNG_BASE_URL in .env
```

**Issue**: Embedding generation fails
```bash
# Check if Ollama is running
ollama list

# Restart Ollama
killall ollama
ollama serve
```

**Issue**: Port already in use
```bash
# Change API_PORT in .env
API_PORT=23801
```

**Issue**: Vector database errors
```bash
# Recreate LanceDB
rm -rf data/lancedb
mkdir -p data/lancedb
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run code formatting
black app/
isort app/

# Run linting
flake8 app/
mypy app/
```

## 📚 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:23800/docs
- **ReDoc**: http://localhost:23800/redoc

## 🗺️ Roadmap

- [ ] **Web UI**: React-based dashboard for research visualization
- [ ] **Multi-language Support**: Research in Chinese, English, and more
- [ ] **Export Formats**: PDF, DOCX, HTML export options
- [ ] **Team Collaboration**: Multi-user research sessions
- [ ] **Advanced Analytics**: Research quality metrics and insights
- [ ] **Plugin System**: Extensible architecture for custom modules
- [ ] **Cloud Deployment**: Docker Compose and Kubernetes configs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangGraph](https://langchain-ai.github.io/langgraph/) - Workflow orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - Modern async web framework
- [LanceDB](https://lancedb.github.io/lancedb/) - Vector database
- [LiteLLM](https://litellm.ai/) - Unified LLM interface
- [DeepSeek](https://platform.deepseek.com/) - AI reasoning models

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/suntianc/ApexBridge-DeepResearch/issues)
- **Discussions**: [GitHub Discussions](https://github.com/suntianc/ApexBridge-DeepResearch/discussions)
- **Email**: Contact via GitHub

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

---

<div align="center">

**Built with ❤️ by the ApexBridge Team**

[Website](https://github.com/suntianc) · [Documentation](https://github.com/suntianc/ApexBridge-DeepResearch/wiki) · [Report Bug](https://github.com/suntianc/ApexBridge-DeepResearch/issues) · [Request Feature](https://github.com/suntianc/ApexBridge-DeepResearch/issues)

</div>
