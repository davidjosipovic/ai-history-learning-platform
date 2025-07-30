#!/bin/bash

# Railway Deployment Script
# Run this script to prepare and deploy to Railway

echo "🚀 Preparing Railway deployment..."

# 1. Create deployment branch
echo "📝 Creating deployment branch..."
git checkout -b railway-deployment 2>/dev/null || git checkout railway-deployment

# 2. Backup current .gitignore
cp .gitignore .gitignore.backup

# 3. Remove books/ from .gitignore for deployment
echo "📚 Adding books to Git for deployment..."
sed -i '/^books\//d' .gitignore

# 4. Add books to git
git add books/
git add .
git commit -m "Prepare for Railway deployment - include books"

echo "✅ Deployment branch ready!"
echo ""
echo "Next steps:"
echo "1. Push to GitHub: git push origin railway-deployment"
echo "2. Go to railway.app and create new project"
echo "3. Connect your GitHub repo"
echo "4. Deploy each service from their respective folders"
echo ""
echo "Environment variables needed:"
echo "AI RAG Service: OPENAI_API_KEY, PORT=8000, PYTHONPATH=/app"
echo "Main API: NODE_ENV=production, AI_RAG_SERVICE_URL"
echo "Frontend: VITE_API_URL, VITE_AI_RAG_URL"
echo ""
echo "To restore development setup:"
echo "git checkout main"
