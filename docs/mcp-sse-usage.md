# MCP Server-Sent Events (SSE) Usage Guide

The **HTTP-based MCP Server** with Server-Sent Events (SSE) provides real-time streaming of semantic search results, specifically designed for **serverless and cloud environments** like Vercel, AWS Lambda, and similar platforms where persistent TCP connections are not available.

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Client Examples](#client-examples)
- [Deployment Considerations](#deployment-considerations)
- [Performance & Best Practices](#performance--best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

### What is SSE MCP?
Server-Sent Events (SSE) is a web standard that allows a server to push data to a client over HTTP. Our MCP SSE implementation provides:
- **Real-time streaming** of search results
- **HTTP/2 compatibility** for improved connection management
- **Serverless-friendly** architecture (no persistent connections)
- **Cross-platform support** (browsers, Node.js, curl, etc.)

### Differences from TCP MCP Server

| Feature | TCP MCP Server | HTTP SSE MCP Server |
|---------|----------------|---------------------|
| **Protocol** | Custom TCP + JSON-RPC | HTTP + Server-Sent Events |
| **Deployment** | Requires persistent connections | Serverless-friendly |
| **Client Support** | Custom TCP clients | Standard HTTP clients |
| **Browser Support** | ❌ No | ✅ Yes (EventSource API) |
| **Firewall/Proxy** | May require special configuration | Works through standard HTTP |
| **Scalability** | Limited by connection pooling | Auto-scales with HTTP infrastructure |

---

## Quick Start

### 1. Start the Server
```bash
# Local development
poetry run uvicorn readwise_vector_db.api:app --reload --host 0.0.0.0 --port 8000

# Or using Docker
docker compose up api
```

### 2. Test with curl
```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8000/mcp/stream?q=machine+learning&k=5"
```

Expected output:
```
event: result
data: {"id": 123, "text": "Machine learning is...", "score": 0.95, "source_type": "article"}

event: result  
data: {"id": 456, "text": "Deep learning algorithms...", "score": 0.89, "source_type": "book"}

event: complete
data: {"total": 2}
```

---

## API Reference

### Endpoint
```
GET /mcp/stream
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | ✅ Yes | - | Search query text |
| `k` | integer | ❌ No | 20 | Number of results (1-100) |
| `source_type` | string | ❌ No | - | Filter by source type |
| `author` | string | ❌ No | - | Filter by author |
| `tags` | string | ❌ No | - | Comma-separated tags filter |
| `highlighted_at_start` | string | ❌ No | - | Start date (ISO format: YYYY-MM-DD) |
| `highlighted_at_end` | string | ❌ No | - | End date (ISO format: YYYY-MM-DD) |

### Response Format

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
Access-Control-Allow-Origin: *
```

**Event Types:**
- `result` - Individual search result
- `complete` - Stream completion with total count
- `error` - Error information

---

## Client Examples

### JavaScript (Browser)

#### Basic Usage
```javascript
// ↳ EventSource provides native SSE support in browsers
const eventSource = new EventSource(
  'http://localhost:8000/mcp/stream?q=artificial%20intelligence&k=10'
);

let results = [];

eventSource.onmessage = function(event) {
  // ↳ Default handler for events without explicit type
  console.log('Received:', event.data);
};

// ↳ Handle specific event types
eventSource.addEventListener('result', function(event) {
  const result = JSON.parse(event.data);
  results.push(result);
  
  console.log(`Found: ${result.text.substring(0, 100)}... (score: ${result.score})`);
});

eventSource.addEventListener('complete', function(event) {
  const completion = JSON.parse(event.data);
  console.log(`Search completed. Total results: ${completion.total}`);
  
  // ↳ Close connection when done
  eventSource.close();
});

eventSource.addEventListener('error', function(event) {
  const error = JSON.parse(event.data);
  console.error('Search error:', error.message);
  eventSource.close();
});

// ↳ Handle connection errors
eventSource.onerror = function(event) {
  console.error('SSE connection error:', event);
  eventSource.close();
};
```

#### With Filters and Error Handling
```javascript
function searchWithFilters(query, options = {}) {
  const params = new URLSearchParams({
    q: query,
    k: options.limit || 20,
    ...(options.sourceType && { source_type: options.sourceType }),
    ...(options.author && { author: options.author }),
    ...(options.tags && { tags: options.tags.join(',') }),
    ...(options.dateRange && {
      highlighted_at_start: options.dateRange.start,
      highlighted_at_end: options.dateRange.end
    })
  });
  
  return new Promise((resolve, reject) => {
    const results = [];
    const eventSource = new EventSource(`/mcp/stream?${params}`);
    
    // ↳ Set timeout to prevent hanging connections
    const timeout = setTimeout(() => {
      eventSource.close();
      reject(new Error('Search timeout'));
    }, 30000);
    
    eventSource.addEventListener('result', (event) => {
      results.push(JSON.parse(event.data));
    });
    
    eventSource.addEventListener('complete', (event) => {
      clearTimeout(timeout);
      eventSource.close();
      resolve(results);
    });
    
    eventSource.addEventListener('error', (event) => {
      clearTimeout(timeout);
      eventSource.close();
      reject(new Error(JSON.parse(event.data).message));
    });
    
    eventSource.onerror = () => {
      clearTimeout(timeout);
      eventSource.close();
      reject(new Error('Connection failed'));
    };
  });
}

// Usage example
searchWithFilters('machine learning', {
  limit: 15,
  sourceType: 'article',
  tags: ['ai', 'research'],
  dateRange: { start: '2024-01-01', end: '2024-12-31' }
}).then(results => {
  console.log(`Found ${results.length} results`);
  results.forEach(r => console.log(r.text));
}).catch(error => {
  console.error('Search failed:', error.message);
});
```

### Node.js

#### Using fetch with async iteration
```javascript
// ↳ Modern approach using fetch and async iteration
async function streamSearch(query, options = {}) {
  const params = new URLSearchParams({
    q: query,
    k: options.limit || 20,
    ...options // Other filter parameters
  });
  
  const response = await fetch(`http://localhost:8000/mcp/stream?${params}`, {
    headers: { 'Accept': 'text/event-stream' }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  const results = [];
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          
          // ↳ Handle different event types based on data content
          if (data.id && data.text) {
            results.push(data); // result event
          } else if (data.total !== undefined) {
            console.log(`Search complete: ${data.total} results`);
            return results; // complete event
          } else if (data.message) {
            throw new Error(data.message); // error event
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
  
  return results;
}

// Usage
(async () => {
  try {
    const results = await streamSearch('neural networks', { limit: 5 });
    console.log('Results:', results);
  } catch (error) {
    console.error('Error:', error.message);
  }
})();
```

#### Using eventsource library
```bash
npm install eventsource
```

```javascript
const EventSource = require('eventsource');

function createSearchStream(query, filters = {}) {
  const params = new URLSearchParams({ q: query, ...filters });
  const url = `http://localhost:8000/mcp/stream?${params}`;
  
  return new EventSource(url);
}

// Usage
const eventSource = createSearchStream('quantum computing', { k: 10 });

eventSource.addEventListener('result', (event) => {
  const result = JSON.parse(event.data);
  console.log(`📖 ${result.text.slice(0, 80)}...`);
});

eventSource.addEventListener('complete', (event) => {
  const { total } = JSON.parse(event.data);
  console.log(`✅ Found ${total} results`);
  eventSource.close();
});

process.on('SIGINT', () => {
  eventSource.close();
  process.exit(0);
});
```

### curl Examples

#### Basic search
```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8000/mcp/stream?q=deep%20learning"
```

#### Search with filters
```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8000/mcp/stream?q=artificial%20intelligence&k=5&source_type=article&author=Yann%20LeCun&tags=ai,research&highlighted_at_start=2024-01-01&highlighted_at_end=2024-12-31"
```

#### Parse results with jq
```bash
curl -s -N -H "Accept: text/event-stream" \
  "http://localhost:8000/mcp/stream?q=machine%20learning&k=3" | \
  grep "^data: " | \
  sed 's/^data: //' | \
  jq -r 'select(.text) | "\(.score): \(.text[0:100])..."'
```

### Python

#### Using httpx with async streaming
```python
import httpx
import json
import asyncio

async def stream_search(query: str, **filters):
    """Stream search results using httpx async client."""
    params = {"q": query, **filters}
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            "http://localhost:8000/mcp/stream",
            params=params,
            headers={"Accept": "text/event-stream"}
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    
                    if "text" in data:  # result event
                        yield data
                    elif "total" in data:  # complete event
                        print(f"Search complete: {data['total']} results")
                        break
                    elif "message" in data:  # error event
                        raise Exception(data["message"])

# Usage
async def main():
    async for result in stream_search(
        "natural language processing",
        k=5,
        source_type="article"
    ):
        print(f"Score {result['score']:.2f}: {result['text'][:100]}...")

asyncio.run(main())
```

#### Using requests with sync streaming
```python
import requests
import json

def search_stream(query: str, **filters):
    """Synchronous streaming search."""
    params = {"q": query, **filters}
    
    with requests.get(
        "http://localhost:8000/mcp/stream",
        params=params,
        headers={"Accept": "text/event-stream"},
        stream=True
    ) as response:
        response.raise_for_status()
        
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                
                if "text" in data:
                    yield data
                elif "total" in data:
                    print(f"Found {data['total']} total results")
                    break

# Usage
for result in search_stream("computer vision", k=3):
    print(f"📄 {result['text'][:80]}... (score: {result['score']})")
```

---

## Deployment Considerations

> 🚀 **For comprehensive deployment instructions across all platforms, see [docs/deployment-sse.md](deployment-sse.md)**

### Why SSE Excels in Serverless Environments

**Key advantages over TCP MCP servers in cloud deployments:**

| Aspect | TCP MCP Server | **SSE MCP Server** |
|--------|----------------|-------------------|
| **Serverless compatibility** | ❌ Requires persistent connections | ✅ Stateless HTTP requests |
| **Auto-scaling** | ⚠️ Limited by connection pooling | ✅ Unlimited horizontal scaling |
| **Cold start resilience** | ❌ Connections drop during restarts | ✅ Automatic reconnection |
| **Infrastructure complexity** | ⚠️ Custom ports, load balancers | ✅ Standard HTTP infrastructure |
| **Global distribution** | ⚠️ Single-region deployments | ✅ Edge network optimization |

### Vercel Deployment
The SSE endpoint works seamlessly on Vercel with these benefits:
- **Auto-scaling**: Handles concurrent connections automatically
- **Edge locations**: Reduced latency via global CDN
- **No connection limits**: HTTP/2 multiplexing supports many clients
- **Zero configuration**: Works out-of-the-box with `vercel.json`

```javascript
// Vercel-optimized client with retry logic
class VercelSSEClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.retryCount = 0;
    this.maxRetries = 3;
  }
  
  async search(query, options = {}) {
    const params = new URLSearchParams({ q: query, ...options });
    
    try {
      const eventSource = new EventSource(`${this.baseUrl}/mcp/stream?${params}`);
      
      return new Promise((resolve, reject) => {
        const results = [];
        
        eventSource.addEventListener('result', (event) => {
          results.push(JSON.parse(event.data));
        });
        
        eventSource.addEventListener('complete', (event) => {
          eventSource.close();
          this.retryCount = 0; // Reset on success
          resolve(results);
        });
        
        eventSource.onerror = (event) => {
          eventSource.close();
          
          if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            setTimeout(() => {
              resolve(this.search(query, options)); // Retry
            }, 1000 * this.retryCount);
          } else {
            reject(new Error('Connection failed after retries'));
          }
        };
      });
    } catch (error) {
      throw new Error(`Search failed: ${error.message}`);
    }
  }
}
```

### Other Serverless Platforms

#### AWS Lambda + API Gateway
```yaml
# serverless.yml snippet
functions:
  api:
    handler: handler.main
    events:
      - http:
          path: /{proxy+}
          method: ANY
          cors: true
    timeout: 30 # ↳ Max Lambda timeout for streaming
```

#### AWS Lambda + API Gateway
```yaml
# serverless.yml snippet
functions:
  api:
    handler: handler.main
    events:
      - http:
          path: /{proxy+}
          method: ANY
          cors: true
    timeout: 30 # ↳ Max Lambda timeout for streaming
```

**Key considerations:**
- Use Mangum for ASGI compatibility
- Configure proper timeout limits (≤ 30s)
- Enable CORS for browser clients
- Consider provisioned concurrency for consistent performance

#### Cloudflare Workers
```javascript
// Workers support SSE via TransformStream
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    if (url.pathname === '/mcp/stream') {
      return handleSSEStream(request, env, ctx);
    }
    
    return new Response('Not found', { status: 404 });
  }
}

function handleSSEStream(request, env, ctx) {
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  
  // Stream results in background
  ctx.waitUntil(streamSearchResults(writer, request, env));
  
  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Access-Control-Allow-Origin': '*'
    }
  });
}
```

**Key considerations:**
- Global edge deployment (automatic)
- CPU time limits (10ms-30s depending on plan)
- Use TransformStream for SSE responses
- Consider Durable Objects for stateful operations

#### Fly.io
```toml
# fly.toml
[http_service]
  internal_port = 8080
  force_https = true
  
  [http_service.concurrency]
    type = "requests"
    hard_limit = 250
    soft_limit = 200
```

**Key considerations:**
- Persistent machines with auto-start/stop
- Multiple regions support
- Health checks for SSE endpoints
- Connection limits for optimal performance

---

## Performance & Best Practices

### HTTP/2 Benefits
Modern browsers and HTTP/2 provide significant advantages:
- **Multiplexing**: Multiple SSE streams over single connection
- **Header compression**: Reduced bandwidth overhead
- **Server push**: Pre-emptive resource delivery

```javascript
// ↳ HTTP/2 allows many concurrent connections efficiently
const MAX_CONCURRENT_SEARCHES = 6; // Browser connection limit
const searchPool = new Map();

async function managedSearch(query, options = {}) {
  const searchId = `${query}-${JSON.stringify(options)}`;
  
  // ↳ Reuse existing search if identical
  if (searchPool.has(searchId)) {
    return searchPool.get(searchId);
  }
  
  const searchPromise = searchWithFilters(query, options);
  searchPool.set(searchId, searchPromise);
  
  try {
    const results = await searchPromise;
    return results;
  } finally {
    searchPool.delete(searchId);
  }
}
```

### Client-Side Optimizations

#### Connection Pooling
```javascript
class SSEConnectionPool {
  constructor(maxConnections = 4) {
    this.maxConnections = maxConnections;
    this.activeConnections = new Set();
    this.waitingQueue = [];
  }
  
  async search(query, options = {}) {
    if (this.activeConnections.size >= this.maxConnections) {
      // ↳ Queue requests when at connection limit
      await new Promise(resolve => this.waitingQueue.push(resolve));
    }
    
    try {
      this.activeConnections.add(query);
      return await this.performSearch(query, options);
    } finally {
      this.activeConnections.delete(query);
      
      // ↳ Process next queued request
      if (this.waitingQueue.length > 0) {
        const next = this.waitingQueue.shift();
        next();
      }
    }
  }
}
```

#### Result Caching
```javascript
class CachedSSEClient {
  constructor() {
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
  }
  
  async search(query, options = {}) {
    const cacheKey = JSON.stringify({ query, options });
    const cached = this.cache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.results; // ↳ Return cached results
    }
    
    const results = await this.performSSESearch(query, options);
    
    this.cache.set(cacheKey, {
      results,
      timestamp: Date.now()
    });
    
    return results;
  }
}
```

### Server-Side Considerations

#### Resource Management
```python
# Example middleware for connection limiting
from fastapi import HTTPException
import asyncio

class ConnectionLimiter:
    def __init__(self, max_connections=100):
        self.max_connections = max_connections
        self.active_connections = 0
        self.semaphore = asyncio.Semaphore(max_connections)
    
    async def __aenter__(self):
        if not await self.semaphore.acquire():
            raise HTTPException(503, "Server busy, try again later")
        self.active_connections += 1
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.active_connections -= 1
        self.semaphore.release()
```

---

## Troubleshooting

### Common Issues

#### 1. Connection Timeouts
**Problem**: EventSource connections timing out in browsers
```javascript
// ↳ Solution: Implement proper timeout handling
const eventSource = new EventSource('/mcp/stream?q=test');

const timeout = setTimeout(() => {
  console.warn('Search taking too long, closing connection');
  eventSource.close();
}, 30000); // 30 second timeout

eventSource.addEventListener('complete', () => {
  clearTimeout(timeout);
  eventSource.close();
});
```

#### 2. CORS Issues in Browsers
**Problem**: Cross-origin requests blocked
```bash
# ↳ Server includes CORS headers by default, but check configuration
curl -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: accept" \
  -X OPTIONS \
  http://localhost:8000/mcp/stream
```

#### 3. Large Result Sets
**Problem**: Memory usage with many results
```javascript
// ↳ Solution: Process results incrementally
eventSource.addEventListener('result', (event) => {
  const result = JSON.parse(event.data);
  
  // Process immediately instead of storing all results
  processResult(result);
  
  // Optionally limit client-side storage
  if (results.length > 1000) {
    results.shift(); // Remove oldest result
  }
});
```

#### 4. Network Interruptions
**Problem**: Connection drops during streaming
```javascript
// ↳ Solution: Implement auto-reconnection
class ReconnectingSSE {
  constructor(url, options = {}) {
    this.url = url;
    this.options = options;
    this.reconnectInterval = options.reconnectInterval || 3000;
    this.maxReconnects = options.maxReconnects || 5;
    this.reconnectCount = 0;
  }
  
  connect() {
    this.eventSource = new EventSource(this.url);
    
    this.eventSource.onopen = () => {
      this.reconnectCount = 0; // Reset on successful connection
    };
    
    this.eventSource.onerror = () => {
      if (this.reconnectCount < this.maxReconnects) {
        this.reconnectCount++;
        setTimeout(() => {
          this.connect(); // Auto-reconnect
        }, this.reconnectInterval);
      }
    };
    
    return this.eventSource;
  }
}
```

### Debug Mode
Enable detailed logging:
```bash
# Set environment variable for detailed SSE logging
export LOG_LEVEL=DEBUG

# Start server with debug info
poetry run uvicorn readwise_vector_db.api:app --log-level debug
```

### Performance Testing
```bash
# Test concurrent connections
for i in {1..10}; do
  curl -s -N -H "Accept: text/event-stream" \
    "http://localhost:8000/mcp/stream?q=test$i&k=5" &
done
wait

# Monitor server resources
docker stats readwise-vector-db_api_1
```

---

## Next Steps

- **Explore the [TCP MCP Server](mcp-tcp-usage.md)** for persistent connection scenarios
- **Check [API Documentation](api-reference.md)** for complete endpoint details  
- **See [Deployment Guide](deployment.md)** for production setup
- **Review [Performance Tuning](performance.md)** for optimization tips 