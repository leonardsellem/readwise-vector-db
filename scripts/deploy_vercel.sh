#!/bin/bash
set -euo pipefail

# Vercel deployment helper script
# Performs pre-deployment validation and deploys to Vercel

echo "🚀 Vercel Deployment Helper"
echo "=========================="

# Check if vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Installing..."
    npm install -g vercel@latest
fi

echo "✅ Vercel CLI found: $(vercel --version)"

# Validate configuration files
echo "🔍 Validating configuration..."

if [[ ! -f "vercel.json" ]]; then
    echo "❌ vercel.json not found"
    exit 1
fi

if [[ ! -f "api/index.py" ]]; then
    echo "❌ api/index.py entry point not found"
    exit 1
fi

if [[ ! -x "vercel_build.sh" ]]; then
    echo "❌ vercel_build.sh is not executable"
    exit 1
fi

echo "✅ Configuration files validated"

# Test build locally first
echo "🛠️ Testing build locally..."
if VERCEL=1 VERCEL_ENV=development ./vercel_build.sh; then
    echo "✅ Local build test passed"
else
    echo "❌ Local build test failed"
    exit 1
fi

# Test entry point import
echo "🔍 Testing ASGI entry point..."
if cd api && python -c "import index; print(f'App type: {type(index.app)}')"; then
    echo "✅ Entry point test passed"
    cd ..
else
    echo "❌ Entry point test failed"
    exit 1
fi

# Check for required environment variables
echo "🔐 Environment variable checklist:"
echo "  - SUPABASE_DB_URL: ${SUPABASE_DB_URL:+✅ Set}${SUPABASE_DB_URL:-❌ Missing}"
echo "  - OPENAI_API_KEY: ${OPENAI_API_KEY:+✅ Set}${OPENAI_API_KEY:-❌ Missing}"
echo "  - READWISE_TOKEN: ${READWISE_TOKEN:+✅ Set}${READWISE_TOKEN:-❌ Missing}"

# Determine deployment type
DEPLOY_TYPE="${1:-preview}"

if [[ "$DEPLOY_TYPE" == "production" ]]; then
    echo "🌟 Deploying to PRODUCTION"
    vercel deploy --prod
elif [[ "$DEPLOY_TYPE" == "preview" ]]; then
    echo "🔍 Deploying PREVIEW"
    vercel deploy
else
    echo "❌ Invalid deployment type: $DEPLOY_TYPE"
    echo "Usage: $0 [preview|production]"
    exit 1
fi

echo "🎉 Deployment completed!"
echo ""
echo "💡 Next steps:"
echo "  1. Test your deployment thoroughly"
echo "  2. Check logs with: vercel logs"
echo "  3. Monitor performance in Vercel dashboard"
