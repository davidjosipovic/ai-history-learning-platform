# Railway Deployment Guide

## Priprema za Railway

### 1. **Dodaj knjige u Git (jedino za deployment)**
```bash
# Ukloni books/ iz .gitignore SAMO za deployment commit
# ili stvori deployment branch

git checkout -b railway-deployment
# Edit .gitignore and remove books/ line
git add books/
git commit -m "Add books for Railway deployment"
```

### 2. **Environment varijable na Railway**
```
OPENAI_API_KEY=sk-your-actual-api-key
PORT=8000
PYTHONPATH=/app
NODE_ENV=production
```

### 3. **Deploy AI RAG Service**
1. Idi na [railway.app](https://railway.app)
2. Stvori novi projekt
3. Connect GitHub repo
4. Odaberi `ai-rag-service` folder
5. Dodaj environment varijable
6. Deploy

### 4. **Deploy Main API**
1. Stvori novi servis u istom projektu
2. Connect isti GitHub repo
3. Odaberi `main-api` folder
4. Dodaj environment varijable:
   ```
   NODE_ENV=production
   AI_RAG_SERVICE_URL=https://your-ai-rag-service.railway.app
   ```

### 5. **Deploy Frontend**
1. Stvori novi servis u istom projektu
2. Connect isti GitHub repo
3. Odaberi `frontend` folder
4. Dodaj environment varijable:
   ```
   VITE_API_URL=https://your-main-api.railway.app
   VITE_AI_RAG_URL=https://your-ai-rag-service.railway.app
   ```

## Alternativno rješenje: Cloud Storage

### **Option A: AWS S3/DigitalOcean Spaces**
```python
# U local_books.py, dodaj funkciju za download iz cloud storage
import boto3

def download_books_from_s3():
    s3 = boto3.client('s3')
    # Download books from S3 bucket
    pass
```

### **Option B: GitHub LFS (Large File Storage)**
```bash
# Setup LFS za velike PDF datoteke
git lfs install
git lfs track "*.pdf"
git add .gitattributes
git add books/
git commit -m "Add books with LFS"
```

### **Option C: Database storage**
- Konvertiraj PDF-ove u tekst i spremi u PostgreSQL
- Railway ima besplatnu PostgreSQL bazu

## Preporučeni workflow:

1. **Development**: Koristi lokalne knjige s docker-compose.yml
2. **Production**: Koristi railway deployment s knjigama u image

```bash
# Za local development
docker-compose up

# Za railway deployment
# Books su već u Docker image, samo deploy
```

## Railway-specific optimizacije:

### 1. **Smaller Docker images**
```dockerfile
# Multi-stage build da smanji image size
FROM python:3.11-slim as base
# ... minimalni dependencies
```

### 2. **Persistent storage**
Railway automatski montira volume za `/app/chroma_db_data`

### 3. **Health checks**
Railway koristi `/health` endpoint za monitoring

## Korisne naredbe:

```bash
# Test Docker image lokalno s baked-in books
docker build -t ai-rag-service ./ai-rag-service
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key ai-rag-service

# Deploy na Railway
railway login
railway link your-project-id
railway up
```

## Troubleshooting:

1. **Knjige se ne učitavaju**: Provjeri da su dodane u Git i Docker image
2. **Memory issues**: Smanji broj chunk-ova ili koristi manje knjiga
3. **Build timeout**: Koristi .dockerignore da isključiš nepotrebne datoteke
