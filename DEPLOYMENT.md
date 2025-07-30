# AI History Learning Platform - Docker Deployment

This guide will help you deploy the AI History Learning Platform using Docker.

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key
- At least 4GB of available RAM
- 10GB of free disk space

## Quick Start

1. **Clone the repository** (if not already done)
   ```bash
   git clone <your-repo-url>
   cd ai-history-learning-platform
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Deploy with one command**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. **Access your application**
   - Frontend: http://localhost
   - Main API: http://localhost:3000
   - AI RAG Service: http://localhost:8000

## Manual Deployment

If you prefer manual steps:

```bash
# 1. Build and start all services
docker-compose up --build -d

# 2. Check logs
docker-compose logs -f

# 3. Stop services
docker-compose down
```

## Services

### 🤖 AI RAG Service (Port 8000)
- **Technology**: Python, FastAPI, ChromaDB
- **Purpose**: Handles AI queries, document processing, and RAG functionality
- **Health Check**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/docs

### 🏗️ Main API (Port 3000)
- **Technology**: Node.js, NestJS
- **Purpose**: Main backend API and business logic
- **Health Check**: http://localhost:3000/health
- **API Docs**: http://localhost:3000/api (if Swagger is configured)

### 🌐 Frontend (Port 80)
- **Technology**: React, Vite, TailwindCSS
- **Purpose**: User interface
- **Health Check**: http://localhost/health

## Data Persistence

- **ChromaDB Data**: Stored in Docker volume `ai_chroma_data`
- **Books**: Local files in `./ai-rag-service/books/` (read-only mount)

## Environment Variables

Create a `.env` file with:

```env
# Required
OPENAI_API_KEY=your_actual_openai_api_key

# Optional (defaults provided)
NODE_ENV=production
PYTHONPATH=/app
AI_RAG_SERVICE_URL=http://ai-rag-service:8000
MAIN_API_URL=http://main-api:3000
```

## Useful Commands

```bash
# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f ai-rag-service

# Restart a specific service
docker-compose restart ai-rag-service

# Rebuild and restart a service
docker-compose up --build -d ai-rag-service

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes ChromaDB data)
docker-compose down -v

# Check service status
docker-compose ps
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs service-name

# Check if port is already in use
netstat -tulpn | grep :8000
```

### Out of memory
```bash
# Check container resource usage
docker stats

# Increase Docker memory limit in Docker Desktop settings
```

### ChromaDB data corruption
```bash
# Reset ChromaDB (⚠️ deletes all data)
docker-compose down -v
docker-compose up -d
```

### API connection issues
- Check that all services are healthy: `docker-compose ps`
- Verify network connectivity between containers
- Check environment variables in containers

## Production Deployment

For production deployment:

1. **Use a reverse proxy** (Nginx, Traefik, or cloud load balancer)
2. **Set up SSL/TLS** certificates
3. **Configure proper logging** and monitoring
4. **Set up backup** for ChromaDB data
5. **Use Docker secrets** for sensitive data
6. **Configure resource limits** in docker-compose.yml

### Example production docker-compose override:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  ai-rag-service:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
    restart: unless-stopped

  main-api:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    restart: unless-stopped

  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M
    restart: unless-stopped
```

Run with: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify your `.env` configuration
3. Ensure Docker has sufficient resources
4. Check that all required ports are available

## Security Notes

- Change default ports in production
- Use environment variables for all secrets
- Keep Docker images updated
- Configure firewall rules appropriately
- Use HTTPS in production
