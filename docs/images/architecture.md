# Architecture Diagram Specification

> **Note:** This file documents what should be in the `architecture.png` diagram.
> Generate the actual PNG using draw.io, Figma, or similar tool.

## Diagram Requirements

### Title: "Readwise Vector DB - Multi-Platform Architecture"

### Layout: Comprehensive system overview with deployment options

## Current System Architecture (2024)

### Overview: Three-Layer Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐│
│  │ Browser     │  │ CLI Tools   │  │ Mobile Apps │  │ Desktop  ││
│  │ EventSource │  │ curl/httpx  │  │ React/Vue   │  │ Apps     ││
│  │ (SSE)       │  │ (HTTP/SSE)  │  │ (HTTP/SSE)  │  │ (TCP)    ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘│
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐│
│  │ /search     │  │ /mcp/stream │  │ /health     │  │ MCP TCP  ││
│  │ (HTTP POST) │  │ (SSE)       │  │ (monitoring)│  │ :8375    ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘│
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ /metrics    │  │ /docs       │  │ /static     │             │
│  │ (Prometheus)│  │ (Swagger)   │  │ (assets)    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Vector DB   │  │ Sync State  │  │ OpenAI      │             │
│  │ (pgvector)  │  │ (cursors)   │  │ Embeddings  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Pattern A: Docker + Local PostgreSQL

```text
┌─────────────────────────────────────────────────────────────────┐
│          🐳 Docker Deployment (Development/Self-hosted)         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │ Readwise    │────▶│ Backfill/   │────▶│ OpenAI      │       │
│  │ API         │     │ Incremental │     │ Embeddings  │       │
│  │ (External)  │     │ Sync Jobs   │     │ (External)  │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                               │                   │             │
│                               ▼                   ▼             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │          Local PostgreSQL 16 + pgvector                │   │
│  │  • highlights table with embedding vectors             │   │
│  │  • sync_state table with cursors                       │   │
│  │  • IVFFlat index for similarity search                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              FastAPI Container (:8000)                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │ /search     │  │ /mcp/stream │  │ /health     │    │   │
│  │  │ (JSON API)  │  │ (SSE)       │  │ (probe)     │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  │  ┌─────────────┐  ┌─────────────┐                     │   │
│  │  │ /metrics    │  │ /docs       │                     │   │
│  │  │ (Prom)      │  │ (Swagger)   │                     │   │
│  │  └─────────────┘  └─────────────┘                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               MCP TCP Server (:8375)                    │   │
│  │  • JSON-RPC 2.0 over persistent TCP                    │   │
│  │  • Streaming search results                            │   │
│  │  • For local AI tools and desktop apps                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Pattern B: Vercel + Supabase (Cloud)

```text
┌─────────────────────────────────────────────────────────────────┐
│           ☁️ Serverless Deployment (Production)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐                           │
│  │ GitHub      │────▶│ Readwise    │                           │
│  │ Actions     │     │ Sync Cron   │                           │
│  │ (Nightly)   │     │ (Workflow)  │                           │
│  └─────────────┘     └─────────────┘                           │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                Vercel Edge Network                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │ Global CDN  │  │ Auto-deploy │  │ Preview     │    │   │
│  │  │ (HTTP/2)    │  │ on tags     │  │ branches    │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              FastAPI Serverless Functions               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │ /search     │  │ /mcp/stream │  │ /health     │    │   │
│  │  │ (JSON API)  │  │ (SSE)       │  │ (probe)     │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  │  • Cold start: <1s                                    │   │
│  │  • Auto-scaling: 0 → ∞                                │   │
│  │  • 30s timeout per request                            │   │
│  │  • Connection pooling optimized                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Supabase Cloud                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │ PostgreSQL  │  │ pgvector    │  │ Connection  │    │   │
│  │  │ 16+         │  │ Extension   │  │ Pooling     │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │
│  │  │ Auto        │  │ Global      │  │ Managed     │    │   │
│  │  │ Backups     │  │ Edge        │  │ Scaling     │    │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Note: TCP MCP Server not available in serverless              │
│        Use /mcp/stream (SSE) for real-time streaming           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Protocol Comparison

| Protocol | Use Case | Deployment | Client Support |
|----------|----------|------------|----------------|
| **HTTP /search** | Standard API queries | Both | Universal |
| **HTTP /mcp/stream (SSE)** | Real-time streaming | Both (preferred serverless) | Browsers, curl, clients |
| **TCP MCP :8375** | Desktop AI tools | Docker only | Custom clients, nc |

### Color Scheme

- **Docker deployment:** Blue theme (#1e40af, #3b82f6)
- **Vercel/Cloud deployment:** Purple theme (#7c3aed, #a855f7)
- **Supabase components:** Green theme (#059669, #10b981)
- **Data flow arrows:** Orange (#ea580c)
- **External services:** Gray theme (#6b7280)
- **Protocol endpoints:** Distinct colors per protocol

### Visual Elements

- **Icons**: Docker whale, cloud symbols, database cylinders
- **Connection types**: Solid lines (HTTP), dashed lines (SSE), dotted lines (TCP)
- **Scaling indicators**: Arrows showing auto-scaling capabilities
- **Performance callouts**: Latency, timeout, and concurrency limits
- **Protocol badges**: Clear labels for HTTP, SSE, TCP endpoints

### Export Settings

- **Format:** PNG and SVG (for scaling)
- **Resolution:** 1400x1000 pixels minimum
- **Background:** White with subtle grid
- **Font:** Inter or similar modern sans-serif (minimum 11pt)
- **Accessibility:** High contrast, colorblind-friendly palette

## Implementation Notes

1. **Two-diagram approach**: Show both deployment patterns side-by-side
2. **Protocol focus**: Emphasize the three different access methods
3. **Cloud-first**: Highlight serverless advantages in the Vercel diagram
4. **Development workflow**: Show how Docker environment mirrors production
5. **Future-ready**: Include space for additional deployment targets

## Validation Checklist

- [ ] Both deployment patterns clearly differentiated
- [ ] All three protocols (HTTP API, SSE, TCP MCP) represented
- [ ] External service dependencies (OpenAI, Readwise) shown
- [ ] Serverless limitations clearly noted (no TCP MCP)
- [ ] Performance characteristics highlighted
- [ ] File size optimized for GitHub (<500KB PNG)
- [ ] Readable on both light and dark GitHub themes
