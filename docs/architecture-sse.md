# SSE MCP Server Architecture

This document describes the architecture patterns for deploying the HTTP-based MCP Server with Server-Sent Events (SSE) across different cloud platforms.

## Architecture Overview

The SSE MCP Server is designed as a **stateless, horizontally-scalable** alternative to traditional TCP-based MCP servers, optimized for serverless and edge deployments.

### Core Architecture Principles

1. **Stateless Design** – No persistent connections or server-side state
2. **HTTP-Native** – Uses standard HTTP/HTTPS for all communication
3. **Event-Driven Streaming** – Real-time results via Server-Sent Events
4. **Auto-Scaling** – Leverages platform auto-scaling capabilities
5. **Edge-Optimized** – Works seamlessly with global CDNs

---

## Deployment Patterns

### 1. Serverless Edge Pattern (Vercel + Supabase)

**Best for:** Global web applications with auto-scaling requirements

```mermaid
flowchart TB
    subgraph "Global Edge Network"
        A[Browser Client] --> B[Vercel Edge Function]
        C[Mobile App] --> B
        D[Desktop App] --> B
    end
    
    subgraph "Vercel Infrastructure"
        B --> E[FastAPI SSE Handler]
        E --> F[Search Service]
        F --> G[OpenAI Embeddings]
    end
    
    subgraph "Supabase Cloud"
        F --> H[PostgreSQL + pgvector]
        I[Connection Pool] --> H
        E --> I
    end
    
    subgraph "SSE Flow"
        E -.-> |"event: result"| A
        E -.-> |"event: complete"| A
        E -.-> |"event: error"| A
    end
    
    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style E fill:#fff3e0
    style H fill:#e8f5e8
```

**Characteristics:**
- ⚡ Sub-100ms global latency via edge locations
- 🔄 Automatic scaling (0 → ∞ concurrent connections)
- 💰 Pay-per-request pricing model
- 🌍 Global distribution included
- ⏱️ Cold start: <1s

---

### 2. Container Orchestration Pattern (Fly.io)

**Best for:** Persistent deployments with predictable traffic patterns

```mermaid
flowchart TB
    subgraph "Global Regions"
        A[Client US-East] --> B[Fly.io US-East]
        C[Client Europe] --> D[Fly.io Europe]
        E[Client Asia] --> F[Fly.io Asia]
    end
    
    subgraph "Fly.io Infrastructure"
        B --> G[SSE Handler Instance]
        D --> H[SSE Handler Instance]
        F --> I[SSE Handler Instance]
        
        G --> J[Shared Database Pool]
        H --> J
        I --> J
    end
    
    subgraph "Database Layer"
        J --> K[Supabase Primary]
        J --> L[Read Replicas]
    end
    
    subgraph "Auto-Scaling"
        M[Traffic Monitor] --> N[Scale Up/Down]
        N --> G
        N --> H
        N --> I
    end
    
    style G fill:#fff3e0
    style H fill:#fff3e0
    style I fill:#fff3e0
    style K fill:#e8f5e8
```

**Characteristics:**
- 🎯 Predictable performance and costs
- 🌐 Multi-region deployment
- 💾 Persistent storage and caching
- 📊 Traditional server monitoring
- ⏱️ Cold start: 0s (persistent)

---

### 3. Hybrid Edge/Origin Pattern (Cloudflare Workers + Lambda)

**Best for:** High-performance applications with complex processing requirements

```mermaid
flowchart TB
    subgraph "Cloudflare Edge"
        A[Global Clients] --> B[Workers SSE Proxy]
        B --> C[Cache Layer]
        B --> D[Rate Limiting]
    end
    
    subgraph "Origin Processing"
        B --> E[AWS Lambda]
        E --> F[Semantic Search]
        F --> G[Vector DB Query]
    end
    
    subgraph "Data Layer"
        G --> H[Supabase/RDS]
        I[OpenAI API] --> F
    end
    
    subgraph "SSE Streaming"
        E -.-> |"Real-time Events"| B
        B -.-> |"event: result"| A
    end
    
    style B fill:#f3e5f5
    style E fill:#fff3e0
    style H fill:#e8f5e8
```

**Characteristics:**
- ⚡ Ultra-low latency via global edge
- 🛡️ Built-in DDoS protection and rate limiting
- 🔄 Smart caching at edge locations
- 💪 Heavy processing at origin
- ⏱️ Cold start: <10ms (edge) + <1s (origin)

---

## SSE Streaming Flow

### Message Flow Architecture

```mermaid
sequenceDiagram
    participant C as Client
    participant E as Edge/Serverless
    participant S as Search Service
    participant DB as Vector Database
    participant AI as OpenAI API
    
    Note over C,AI: SSE Connection Establishment
    C->>+E: GET /mcp/stream?q=query
    E->>C: Headers: text/event-stream
    
    Note over C,AI: Search Processing
    E->>+S: Execute search
    S->>+AI: Generate embedding
    AI-->>-S: Embedding vector
    
    Note over C,AI: Streaming Results
    loop For each result
        S->>+DB: Vector similarity query
        DB-->>-S: Search result
        S->>E: Result data
        E-->>C: event: result\ndata: {...}
    end
    
    Note over C,AI: Completion
    S->>-E: Search complete
    E-->>C: event: complete\ndata: {"total": N}
    E-->>-C: Connection closed
```

### Connection Lifecycle

1. **Connection Establishment**
   - Client opens SSE connection with `EventSource`
   - Server validates parameters and sets streaming headers
   - Platform handles auto-scaling and load balancing

2. **Real-time Streaming**
   - Search service streams results as they're found
   - Each result emitted as separate SSE event
   - Platform handles back-pressure and client disconnects

3. **Graceful Completion**
   - Completion event with total count
   - Connection closed by server
   - Client can immediately reconnect for new searches

---

## Platform-Specific Optimizations

### Vercel Optimizations

```mermaid
flowchart LR
    subgraph "Request Path"
        A[EventSource] --> B[Edge Cache]
        B --> C[Serverless Function]
        C --> D[Database Pool]
    end
    
    subgraph "Optimizations"
        E[HTTP/2 Multiplexing]
        F[Edge Regions]
        G[Auto-scaling]
        H[Cold Start <1s]
    end
    
    B -.-> E
    C -.-> F
    C -.-> G
    C -.-> H
```

**Key features:**
- Edge caching for static responses
- HTTP/2 multiplexing support
- Automatic HTTPS and CDN
- Zero-config deployments

### AWS Lambda Optimizations

```mermaid
flowchart LR
    subgraph "AWS Infrastructure"
        A[API Gateway] --> B[Lambda Function]
        B --> C[RDS Proxy]
        C --> D[Aurora Serverless]
    end
    
    subgraph "Performance"
        E[Provisioned Concurrency]
        F[Connection Pooling]
        G[Regional Deployment]
    end
    
    B -.-> E
    C -.-> F
    A -.-> G
```

**Key features:**
- Provisioned concurrency for consistent performance
- RDS Proxy for connection pooling
- Integration with AWS ecosystem
- Fine-grained cost control

### Cloudflare Workers Optimizations

```mermaid
flowchart LR
    subgraph "Edge Computing"
        A[Worker Script] --> B[Global Network]
        B --> C[Origin API]
    end
    
    subgraph "Features"
        D[200+ Edge Locations]
        E[10ms Startup]
        F[Durable Objects]
        G[KV Storage]
    end
    
    A -.-> D
    A -.-> E
    B -.-> F
    B -.-> G
```

**Key features:**
- Instant cold starts
- Global edge deployment
- TransformStream for SSE
- Integrated caching and storage

---

## Performance Characteristics

### Latency Comparison

| Platform | Cold Start | Warm Request | Global Reach | Concurrent Streams |
|----------|------------|--------------|--------------|-------------------|
| **Vercel** | <1s | <50ms | ✅ Edge | Unlimited |
| **AWS Lambda** | <500ms | <10ms | ⚠️ Regional | 1000/region |
| **Cloudflare Workers** | <10ms | <5ms | ✅ Global | Unlimited |
| **Fly.io** | 0s | <20ms | ✅ Multi-region | 250/instance |

### Scaling Patterns

**Horizontal Scaling (Serverless):**
```
Concurrent Connections: 1 → 10 → 100 → 1000+ (automatic)
Cost: Linear with usage
Latency: Consistent
Management: Zero
```

**Vertical Scaling (Containers):**
```
Instance Size: Small → Medium → Large (manual/auto)
Cost: Fixed baseline + scaling
Latency: Predictable
Management: Traditional ops
```

---

## Security Considerations

### Transport Security
- **TLS/HTTPS:** Mandatory for all platforms
- **Headers:** Security headers automatically applied
- **CORS:** Configurable origin restrictions
- **Rate Limiting:** Platform-native or custom implementation

### Authentication Patterns

```mermaid
flowchart TB
    A[Client Request] --> B{Auth Required?}
    B -->|Yes| C[API Key/JWT Validation]
    B -->|No| D[Public Access]
    C --> E[SSE Stream]
    D --> E
    
    subgraph "Auth Options"
        F[API Keys]
        G[JWT Tokens] 
        H[OAuth 2.0]
        I[Custom Headers]
    end
    
    C -.-> F
    C -.-> G
    C -.-> H
    C -.-> I
```

### Data Privacy
- **In-transit:** TLS 1.2+ encryption
- **At-rest:** Database-level encryption (Supabase/AWS)
- **Logs:** Configurable retention and redaction
- **Compliance:** GDPR/SOC2 via platform compliance

---

## Monitoring & Observability

### Key Metrics

```mermaid
flowchart TB
    subgraph "Application Metrics"
        A[SSE Connection Count]
        B[Stream Duration]
        C[Search Latency]
        D[Error Rates]
    end
    
    subgraph "Platform Metrics"
        E[Cold Start Frequency]
        F[Resource Utilization]
        G[Regional Distribution]
        H[Cost per Request]
    end
    
    subgraph "Business Metrics"
        I[Daily Active Connections]
        J[Query Volume]
        K[User Satisfaction]
        L[Feature Adoption]
    end
```

### Monitoring Stack

**Built-in Platform Monitoring:**
- Vercel Analytics & Logs
- AWS CloudWatch
- Cloudflare Analytics
- Fly.io Metrics

**Custom Application Metrics:**
- Prometheus endpoints (`/metrics`)
- OpenTelemetry tracing
- Structured logging
- Health check endpoints

---

This architecture enables the SSE MCP server to provide real-time, scalable search capabilities across diverse deployment environments while maintaining optimal performance and cost efficiency. 