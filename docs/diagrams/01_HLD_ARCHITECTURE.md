# HLD Architecture - AVI System

> High-Level Design of the AVI (Agreement Validation Interface) System

**Version**: 1.0 (Release Candidate)
**Date**: 2025-11-19
**Status**: Production Ready

---

## System Architecture

```mermaid
graph TB
    subgraph "External Services"
        User[Users/Clients]
        LLM[External LLM APIs<br/>OpenAI, Anthropic, etc.]
    end

    subgraph "AVI Platform"
        subgraph "User Interface"
            GradioUI[Gradio Chat UI<br/>Port 7860]
        end

        subgraph "API Layer"
            FastAPI[FastAPI Application<br/>Port 8000]
        end

        subgraph "Core Services"
            ContentFilter[Content Filter<br/>Vector Rules + Safety]
            RAGSystem[RAG System<br/>Context Retrieval]
            LLMService[LLM Service<br/>Query Processing]
        end

        subgraph "Data Storage"
            VectorDB[(Vector Database<br/>Qdrant/ChromaDB<br/>Port 6333)]
            Redis[(Redis Cache<br/>Port 6379)]
        end

        subgraph "Benchmarking"
            BenchmarkScript[Benchmark Script<br/>scripts/benchmark_indexing.py]
        end
    end

    %% User interactions
    User -->|HTTP| GradioUI
    User -->|REST API| FastAPI
    GradioUI --> FastAPI

    %% API to services
    FastAPI --> ContentFilter
    FastAPI --> RAGSystem
    FastAPI --> LLMService

    %% Services to storage
    ContentFilter --> VectorDB
    RAGSystem --> VectorDB
    RAGSystem --> Redis
    LLMService --> Redis

    %% LLM integration
    LLMService --> LLM

    %% Benchmarking
    BenchmarkScript --> VectorDB

    %% Styling
    classDef ui fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef api fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef storage fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef external fill:#eceff1,stroke:#263238,stroke-width:2px
    classDef benchmark fill:#fff9c4,stroke:#f57f17,stroke-width:2px

    class GradioUI ui
    class FastAPI api
    class ContentFilter,RAGSystem,LLMService service
    class VectorDB,Redis storage
    class User,LLM external
    class BenchmarkScript benchmark
```

---

## Query Processing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Gradio UI
    participant API as FastAPI
    participant Cache as Redis
    participant Filter as Content Filter
    participant VDB as Vector DB
    participant RAG as RAG System
    participant LLM as External LLM

    U->>UI: Send query
    UI->>API: POST /api/v1/query

    API->>Cache: Check cache
    alt Cache hit
        Cache-->>API: Return cached response
    else Cache miss
        API->>Filter: Input filtering
        Filter->>VDB: Vector search (rules)
        VDB-->>Filter: Matching rules

        alt Query is safe
            API->>RAG: Get context
            RAG->>VDB: Vector search (documents)
            VDB-->>RAG: Relevant documents
            RAG-->>API: Context

            API->>LLM: Generate response
            LLM-->>API: LLM response

            API->>Filter: Output filtering
            Filter-->>API: Safe response

            API->>Cache: Store result
        else Query blocked
            Filter-->>API: Blocked response
        end
    end

    API-->>UI: Response
    UI-->>U: Display result
```

---

## Components

### User Interface

**Gradio Chat UI**
- **Port**: 7860
- **Features**:
  - Real-time chat interface
  - RAG toggle (on/off)
  - Safety filters toggle
  - Rule and document management

### API Layer

**FastAPI Application**
- **Port**: 8000
- **Documentation**: `/docs` (Swagger UI)
- **Key Endpoints**:
  - `POST /api/v1/query` - Process queries
  - `POST /api/v1/chat/stream` - Streaming chat
  - `POST /api/v1/upload/csv` - Upload data
  - `POST /api/v1/reindex` - Reindex database
  - `GET /api/v1/health` - Health check

### Core Services

**Content Filter**
- Vector-based rule matching
- Input/output filtering
- Safety LLM integration (optional)

**RAG System**
- Context retrieval from vector DB
- Document reranking
- Relevance scoring

**LLM Service**
- OpenAI-compatible API support
- Streaming responses
- Mock mode for testing

### Data Storage

**Vector Database (Qdrant/ChromaDB)**
- Collections: `filter_rules`, `vector_documents`, `links`
- Port: 6333 (Qdrant)

**Redis Cache**
- Query result caching
- Port: 6379

### Benchmarking

**Benchmark Script**
- `scripts/benchmark_indexing.py`
- Tests both ChromaDB and Qdrant
- Measures indexing time and memory
- Outputs results to `data/benchmarks/`

---

## Data Flow

1. **User Query** -> Gradio UI or direct API call
2. **Cache Check** -> Return if cached
3. **Input Filter** -> Block unsafe queries
4. **RAG Retrieval** -> Get relevant context
5. **LLM Generation** -> Generate response
6. **Output Filter** -> Sanitize response
7. **Cache Store** -> Save for future
8. **Return** -> Safe, grounded answer

---

## Deployment

### Docker Compose (Recommended)

```bash
docker compose up --build
```

Services:
- `api` - FastAPI backend (8000)
- `qdrant` - Vector database (6333)
- `redis` - Cache (6379)

### Local Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload
python gradio_ui.py
```

---

**Version**: 1.0 (Release Candidate)
**Date**: 2025-11-19
**Status**: Production Ready
