# SSE MCP Server Deployment Guide

This guide covers deploying the **HTTP-based MCP Server with Server-Sent Events (SSE)** to various serverless and cloud platforms. The SSE endpoint provides real-time streaming of search results without requiring persistent TCP connections.

## Table of Contents
- [Overview](#overview)
- [Platform-Specific Deployments](#platform-specific-deployments)
  - [Vercel + Supabase](#vercel--supabase)
  - [AWS Lambda + API Gateway](#aws-lambda--api-gateway)
  - [Cloudflare Workers](#cloudflare-workers)
  - [Fly.io](#flyio)
  - [Railway](#railway)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)

---

## Overview

### Why SSE for Serverless MCP?

The **HTTP SSE MCP Server** is specifically designed for serverless environments where traditional TCP connections are not supported or impractical:

**✅ Advantages over TCP MCP:**
- **Serverless native** – Works on Vercel, Lambda, Workers, etc.
- **Auto-scaling** – Handles unlimited concurrent connections
- **Firewall friendly** – Uses standard HTTP/HTTPS ports
- **Browser compatible** – EventSource API support
- **HTTP/2 optimized** – Multiplexing and header compression
- **Cold-start resilient** – No persistent state required

**🎯 Perfect for:**
- Production web applications
- Browser-based AI tools
- Multi-tenant SaaS platforms
- Global edge deployments
- Auto-scaling workloads

---

## Platform-Specific Deployments

### Vercel + Supabase

**Recommended for:** Production web applications with global edge distribution

#### Quick Setup
```bash
# 1. Clone and setup
git clone <your-repo>
cd readwise-vector-db

# 2. Configure environment
cp .env.supabase.example .env
# Edit .env with your Supabase credentials

# 3. Deploy to Vercel
vercel login
vercel link
vercel env add SUPABASE_DB_URL
vercel env add OPENAI_API_KEY  
vercel env add READWISE_TOKEN
vercel --prod
```

#### Configuration Details

**vercel.json** (auto-configured):
```json
{
  "buildCommand": "./vercel_build.sh",
  "env": {
    "DEPLOY_TARGET": "vercel",
    "DB_BACKEND": "supabase"
  },
  "functions": {
    "api/index.py": {
      "runtime": "python3.12",
      "maxDuration": 30
    }
  },
  "headers": [
    {
      "source": "/mcp/stream",
      "headers": [
        { "key": "Cache-Control", "value": "no-cache, no-transform" },
        { "key": "Connection", "value": "keep-alive" },
        { "key": "Access-Control-Allow-Origin", "value": "*" }
      ]
    }
  ]
}
```

**Environment Variables:**
```bash
# Required
SUPABASE_DB_URL="postgresql://postgres:[password]@db.[project].supabase.co:6543/postgres"
OPENAI_API_KEY="sk-..."
READWISE_TOKEN="..."

# Automatic (Vercel sets these)
DEPLOY_TARGET="vercel"
DB_BACKEND="supabase"

# Optional tuning
MCP_SSE_HEARTBEAT_MS="30000"  # 30s heartbeat
MCP_STREAM_TIMEOUT="25"       # 25s timeout (5s buffer for Vercel 30s limit)
```

#### Verification
```bash
# Test the deployed endpoint
curl -N -H "Accept: text/event-stream" \
  "https://your-app.vercel.app/mcp/stream?q=test&k=3"

# Expected output:
# event: result
# data: {"id": 123, "text": "...", "score": 0.95}
# 
# event: complete  
# data: {"total": 3}
```

---

### AWS Lambda + API Gateway

**Recommended for:** AWS-native deployments with existing infrastructure

#### Setup with SAM
```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    Runtime: python3.12

Resources:
  ReadwiseVectorAPI:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: api.lambda_handler.handler
      Environment:
        Variables:
          DEPLOY_TARGET: "lambda" 
          DB_BACKEND: "supabase"
          SUPABASE_DB_URL: !Ref SupabaseDBURL
          OPENAI_API_KEY: !Ref OpenAIAPIKey
      Events:
        HttpApi:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Method: GET
            Path: /mcp/stream

  HttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins: ["*"]
        AllowMethods: ["GET", "POST", "OPTIONS"]
        AllowHeaders: ["Content-Type", "Accept"]

Parameters:
  SupabaseDBURL:
    Type: String
    NoEcho: true
  OpenAIAPIKey:
    Type: String
    NoEcho: true
```

#### Lambda Handler
```python
# api/lambda_handler.py
import asyncio
from mangum import Mangum
from readwise_vector_db.api import get_application

app = get_application()
handler = Mangum(app, lifespan="off")

# For streaming SSE responses
def lambda_handler(event, context):
    # Mangum handles SSE streaming automatically
    return handler(event, context)
```

#### Deploy Commands
```bash
# Install SAM CLI
pip install aws-sam-cli

# Build and deploy
sam build
sam deploy --guided \
  --parameter-overrides \
  SupabaseDBURL="postgresql://..." \
  OpenAIAPIKey="sk-..."
```

---

### Cloudflare Workers

**Recommended for:** Global edge deployment with minimal latency

#### Worker Script
```javascript
// workers/mcp-stream.js
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    if (url.pathname === '/mcp/stream') {
      return handleSSEStream(request, env);
    }
    
    return new Response('Not found', { status: 404 });
  }
};

async function handleSSEStream(request, env) {
  const query = url.searchParams.get('q');
  if (!query) {
    return new Response('Missing query parameter', { status: 400 });
  }

  // Create a readable stream for SSE
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  
  // Start streaming in background
  ctx.waitUntil(streamResults(writer, query, env));
  
  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*'
    }
  });
}

async function streamResults(writer, query, env) {
  try {
    // Call your Python API or implement search directly
    const response = await fetch(`${env.PYTHON_API_URL}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q: query })
    });
    
    const results = await response.json();
    
    for (const result of results) {
      await writer.write(`event: result\ndata: ${JSON.stringify(result)}\n\n`);
    }
    
    await writer.write(`event: complete\ndata: {"total": ${results.length}}\n\n`);
  } catch (error) {
    await writer.write(`event: error\ndata: {"message": "${error.message}"}\n\n`);
  } finally {
    await writer.close();
  }
}
```

#### wrangler.toml
```toml
name = "readwise-mcp-sse"
main = "workers/mcp-stream.js"
compatibility_date = "2024-01-01"

[env.production.vars]
PYTHON_API_URL = "https://your-python-api.vercel.app"

[env.production.secrets]
OPENAI_API_KEY = "sk-..."
```

#### Deploy
```bash
npm install -g wrangler
wrangler login
wrangler publish
```

---

### Fly.io

**Recommended for:** Persistent deployments with global regions

#### fly.toml
```toml
app = "readwise-vector-sse"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile.fly"

[env]
  DEPLOY_TARGET = "fly"
  DB_BACKEND = "supabase"
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true

  [http_service.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200

[[http_service.checks]]
  interval = "10s"
  timeout = "5s"
  grace_period = "5s"
  method = "GET"
  path = "/health"

# SSE-specific configuration
[[services]]
  http_checks = []
  internal_port = 8080
  processes = ["app"]
  protocol = "tcp"
  script_checks = []

  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.tcp_checks]]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"
```

#### Dockerfile.fly
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main

# Copy application
COPY . .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["uvicorn", "readwise_vector_db.api:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Deploy
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Setup and deploy
fly auth login
fly launch
fly secrets set SUPABASE_DB_URL="postgresql://..."
fly secrets set OPENAI_API_KEY="sk-..."
fly deploy
```

---

### Railway

**Recommended for:** Simple deployments with automatic CI/CD

#### railway.json
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE"
  }
}
```

#### Environment Setup
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and setup
railway login
railway init
railway link

# Set environment variables
railway variables set DEPLOY_TARGET=railway
railway variables set DB_BACKEND=supabase  
railway variables set SUPABASE_DB_URL="postgresql://..."
railway variables set OPENAI_API_KEY="sk-..."

# Deploy
railway up
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEPLOY_TARGET` | ✅ | `docker` | Deployment platform (`vercel`, `lambda`, `fly`, etc.) |
| `DB_BACKEND` | ✅ | `local` | Database backend (`supabase`, `local`) |
| `SUPABASE_DB_URL` | ✅* | - | Supabase connection string (*when `DB_BACKEND=supabase`) |
| `OPENAI_API_KEY` | ✅ | - | OpenAI API key for embeddings |
| `MCP_SSE_HEARTBEAT_MS` | ❌ | `30000` | SSE heartbeat interval (milliseconds) |
| `MCP_STREAM_TIMEOUT` | ❌ | `30` | Stream timeout (seconds) |
| `MCP_ALLOWED_ORIGINS` | ❌ | `*` | CORS allowed origins |
| `MCP_MAX_CONNECTIONS` | ❌ | `100` | Max concurrent SSE connections |

### Headers Configuration

**Required Headers for SSE:**
```http
Content-Type: text/event-stream
Cache-Control: no-cache, no-transform
Connection: keep-alive
Access-Control-Allow-Origin: *
```

**Platform-specific optimizations:**

**Vercel:**
```json
{
  "headers": [
    {
      "source": "/mcp/stream",
      "headers": [
        { "key": "Cache-Control", "value": "no-cache, no-transform" },
        { "key": "X-Accel-Buffering", "value": "no" }
      ]
    }
  ]
}
```

**AWS API Gateway:**
```yaml
ResponseParameters:
  method.response.header.Cache-Control: "'no-cache'"
  method.response.header.Connection: "'keep-alive'"
```

---

## Troubleshooting

### Common Issues

#### 1. Premature Connection Close
**Symptoms:** SSE stream ends after 10-30 seconds
```bash
# Diagnostic
curl -v -N -H "Accept: text/event-stream" \
  "https://your-app.com/mcp/stream?q=test" 2>&1 | grep -E "(HTTP|Connection|close)"
```

**Solutions:**
- Increase `MCP_STREAM_TIMEOUT` (but stay under platform limits)
- Add heartbeat events every 30 seconds
- Check platform-specific timeout settings

#### 2. 502 Bad Gateway on Idle
**Symptoms:** First request after idle period fails
```bash
# Test cold start
curl -w "%{http_code}" "https://your-app.com/health"
sleep 60
curl -w "%{http_code}" "https://your-app.com/mcp/stream?q=test"
```

**Solutions:**
- Implement proper health checks
- Use platform keep-warm features
- Add retry logic to clients

#### 3. CORS Configuration Issues
**Symptoms:** Browser requests blocked by CORS policy
```javascript
// Test in browser console
fetch('/mcp/stream?q=test', {
  headers: { 'Accept': 'text/event-stream' }
}).then(r => console.log(r.headers.get('Access-Control-Allow-Origin')));
```

**Solutions:**
- Verify `Access-Control-Allow-Origin` header
- Check preflight OPTIONS handling
- Update platform CORS configuration

#### 4. Large Response Buffering
**Symptoms:** Results arrive all at once instead of streaming
```bash
# Check streaming behavior
curl -N -H "Accept: text/event-stream" \
  "https://your-app.com/mcp/stream?q=test&k=50" | \
  while read line; do echo "$(date): $line"; done
```

**Solutions:**
- Add `X-Accel-Buffering: no` header (Nginx/Vercel)
- Disable proxy buffering
- Check platform streaming settings

### Debug Commands

**Test SSE endpoint:**
```bash
# Basic connectivity
curl -I "https://your-app.com/mcp/stream?q=test"

# Full stream test  
curl -N -H "Accept: text/event-stream" \
  "https://your-app.com/mcp/stream?q=test&k=3" | \
  head -20

# Timing analysis
time curl -N -H "Accept: text/event-stream" \
  "https://your-app.com/mcp/stream?q=test&k=1" | \
  grep -m1 "event: complete"
```

**Platform-specific diagnostics:**

**Vercel:**
```bash
# Check function logs
vercel logs --follow

# Test edge regions
curl -H "Accept: text/event-stream" \
  "https://your-app.vercel.app/mcp/stream?q=test" \
  -H "X-Vercel-Region: iad1"
```

**AWS Lambda:**
```bash
# CloudWatch logs
aws logs tail /aws/lambda/your-function --follow

# API Gateway test
aws apigatewayv2 test-invoke-route --api-id YOUR_API_ID \
  --route-key "GET /mcp/stream"
```

---

## Performance Tuning

### Connection Management

**Optimize for high concurrency:**
```python
# readwise_vector_db/config.py
class Settings(BaseSettings):
    # Serverless-optimized pooling
    database_pool_size: int = 1 if is_serverless else 5
    database_max_overflow: int = 4 if is_serverless else 10
    
    # SSE-specific tuning
    mcp_sse_heartbeat_ms: int = 30000
    mcp_stream_timeout: int = 25  # Platform timeout - 5s buffer
    mcp_max_connections: int = 100
```

**Client-side optimization:**
```javascript
// Implement connection pooling
class SSEConnectionManager {
  constructor(maxConnections = 6) {
    this.maxConnections = maxConnections;
    this.activeStreams = new Set();
    this.waitQueue = [];
  }
  
  async createStream(query, options = {}) {
    if (this.activeStreams.size >= this.maxConnections) {
      await this.waitForAvailableSlot();
    }
    
    const stream = new EventSource(`/mcp/stream?${new URLSearchParams({
      q: query,
      ...options
    })}`);
    
    this.activeStreams.add(stream);
    
    stream.addEventListener('close', () => {
      this.activeStreams.delete(stream);
      this.processWaitQueue();
    });
    
    return stream;
  }
}
```

### Platform-Specific Optimizations

**Vercel:**
- Use HTTP/2 multiplexing (automatic)
- Enable edge caching for static responses
- Optimize cold start with smaller bundles

**AWS Lambda:**
- Provision concurrency for consistent performance
- Use Lambda@Edge for global distribution
- Implement connection keep-alive

**Cloudflare Workers:**
- Leverage global edge network (automatic)
- Use Durable Objects for stateful operations
- Implement smart caching strategies

---

## Monitoring & Observability

### Health Checks

**Endpoint monitoring:**
```bash
# Simple health check
curl -f "https://your-app.com/health"

# SSE-specific check
timeout 10 curl -N -H "Accept: text/event-stream" \
  "https://your-app.com/mcp/stream?q=test&k=1" | \
  grep -q "event: complete" && echo "SSE OK" || echo "SSE FAILED"
```

### Metrics Collection

**Key metrics to monitor:**
- SSE connection count
- Stream duration distribution  
- Error rates by platform
- Cold start latency
- Database connection pool usage

**Prometheus metrics (built-in):**
```bash
# Check metrics endpoint
curl "https://your-app.com/metrics" | grep mcp_
```

---

This deployment guide ensures your SSE MCP server runs optimally across all major serverless platforms. For additional platform-specific configurations, refer to the respective platform documentation. 