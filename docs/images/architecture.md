# Architecture Diagram Specification

> **Note:** This file documents what should be in the `architecture.png` diagram.
> Generate the actual PNG using draw.io, Figma, or similar tool.

## Diagram Requirements

### Title: "Readwise Vector DB - Deployment Architectures"

### Layout: Side-by-side comparison

#### Left Side: Docker + Local PostgreSQL (Default)
```
┌─────────────────────────────────────┐
│          🐳 Docker Deployment       │
├─────────────────────────────────────┤
│  ┌─────────────┐                    │
│  │ Readwise    │ ──┐                │
│  │ API         │   │                │
│  └─────────────┘   │                │
│                     ▼                │
│  ┌─────────────┐  ┌──────────────┐   │
│  │ Nightly     │  │ OpenAI       │   │
│  │ Cron Job    │  │ Embeddings   │   │
│  └─────────────┘  └──────────────┘   │
│         │                 │          │
│         ▼                 ▼          │
│  ┌─────────────────────────────────┐ │
│  │ Local PostgreSQL + pgvector    │ │
│  └─────────────────────────────────┘ │
│                     │                │
│                     ▼                │
│  ┌─────────────────────────────────┐ │
│  │ FastAPI Container (:8000)       │ │
│  │  • /health                      │ │
│  │  • /search                      │ │
│  │  • /docs                        │ │
│  │  • /metrics                     │ │
│  └─────────────────────────────────┘ │
│                     │                │
│                     ▼                │
│  ┌─────────────────────────────────┐ │
│  │ MCP Server (:8375)              │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

#### Right Side: Vercel + Supabase (Cloud)
```
┌─────────────────────────────────────┐
│       ☁️ Serverless Deployment     │
├─────────────────────────────────────┤
│  ┌─────────────┐                    │
│  │ GitHub      │ ──┐                │
│  │ Actions     │   │                │
│  └─────────────┘   │                │
│                     ▼                │
│  ┌─────────────────────────────────┐ │
│  │ Vercel Edge Functions           │ │
│  │  • Auto-deploy on tags         │ │
│  │  • Preview deployments         │ │
│  │  • 30s timeout per request     │ │
│  └─────────────────────────────────┘ │
│                     │                │
│                     ▼                │
│  ┌─────────────────────────────────┐ │
│  │ FastAPI Serverless              │ │
│  │  • /health                      │ │
│  │  • /search                      │ │
│  │  • /docs                        │ │
│  └─────────────────────────────────┘ │
│                     │                │
│                     ▼                │
│  ┌─────────────────────────────────┐ │
│  │ Supabase PostgreSQL             │ │
│  │  • Managed pgvector             │ │
│  │  • Automated backups            │ │
│  │  • Global edge network          │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Color Scheme
- **Docker side:** Blue theme (#0066CC)
- **Vercel side:** Black/Purple theme (#000000, #7C3AED)
- **Shared components:** Green theme (#059669)
- **Data flow arrows:** Orange (#EA580C)

### Key Visual Elements
- Container icons for Docker components
- Cloud icons for Vercel/Supabase
- Database cylinder for PostgreSQL
- API endpoint boxes
- Clear directional arrows showing data flow
- Environment variable callouts where relevant

### Export Settings
- **Format:** PNG
- **Resolution:** 1200x800 pixels
- **Background:** White
- **Font:** Clear, readable sans-serif (minimum 10pt)

## Implementation
1. Create diagram in draw.io, Figma, or Lucidchart
2. Export as PNG to `docs/images/architecture.png`
3. Ensure file size < 500KB for fast GitHub loading
4. Test visibility on both light and dark GitHub themes
