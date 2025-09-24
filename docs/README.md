# Smart Vault API - Docker Setup Guide

This guide provides comprehensive instructions for setting up and running the Smart Vault API project using Docker and Docker Compose.

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)
- [Production Considerations](#production-considerations)

## 🚀 Project Overview

The Smart Vault API is a FastAPI-based application that provides secure vault management with the following features:

- **User Management**: Authentication, authorization, and user roles
- **Vault Operations**: Create, manage, and share digital vaults
- **Security Features**: JWT authentication, brute force protection, audit logging
- **Real-time Updates**: WebSocket support for live log streaming
- **Access Control**: NFC card and keypad PIN authentication
- **Redis Integration**: Caching and session management

### Architecture

- **Backend**: FastAPI with SQLAlchemy ORM
- **Database**: MySQL (or SQLite for development)
- **Cache/Session Store**: Redis
- **WebSockets**: Real-time log streaming
- **Authentication**: JWT tokens with role-based access control

## 📋 Prerequisites

Before setting up the project, ensure you have the following installed:

- **Docker** (version 20.10 or later)
- **Docker Compose** (version 2.0 or later)
- **Git** (for cloning the repository)

### Install Docker

#### Windows
1. Download Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/)
2. Run the installer and restart your machine
3. Verify installation: `docker --version`

#### macOS
1. Download Docker Desktop for Mac from [docker.com](https://docs.docker.com/desktop/mac/install/)
2. Follow the installation instructions
3. Verify installation: `docker --version`

#### Linux (Ubuntu/Debian)
```bash
# Update package index
sudo apt-get update

# Install packages to allow apt to use HTTPS
sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up stable repository
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group (optional)
sudo usermod -aG docker $USER

# Verify installation
docker --version
```

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd smartvault-api
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your configuration:
   - MySQL
   ```env
   DATABASE_URL=mysql+pymysql://root:yourpassword@db:3306/smartvault
   REDIS_URL=redis://redis:6379
   JWT_SECRET=your-super-secret-jwt-key-here
   DEBUG=true
   ```
   - SqLite
   ```env
   DATABASE_URL=sqlite:///./smartvault.db
   REDIS_URL=redis://localhost:6379
   JWT_SECRET=your-super-secret-jwt-key-here
   DEBUG=true
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

5. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Redis: localhost:6379

## 📦 Detailed Setup

### Step 1: Clone and Navigate

```bash
git clone <repository-url>
cd smartvault-api
```

### Step 2: Environment Configuration

Create a `.env` file based on the example:

```bash
cp .env.example .env
```

Edit the `.env` file with appropriate values:

```env
# Database Configuration
DATABASE_URL=mysql+pymysql://root:yourpassword@db:3306/smartvault

# Redis Configuration
REDIS_URL=redis://redis:6379

# Security
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production

# Application Settings
DEBUG=true
ENVIRONMENT=development

# Optional: Database backup settings
DB_BACKUP_PATH=/app/backups
```

### Step 3: Docker Services Overview

The `docker-compose.yml` defines the following services:

- **api**: FastAPI application container
- **redis**: Redis cache and session store

### Step 4: Build and Start Services

```bash
# Build and start all services
docker-compose up --build -d

# Or start without building (if images already exist)
docker-compose up -d
```

### Step 5: Verify Services

```bash
# Check running containers
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f redis

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Step 6: Database Setup

The application uses Alembic for database migrations:

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Check current revision
docker-compose exec api alembic current

# View migration history
docker-compose exec api alembic history
```

### Step 7: Access the Application

- **API Base URL**: http://localhost:8000
- **Interactive Documentation**: http://localhost:8000/docs
- **Alternative Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🔧 Environment Configuration

### Database Options

The application supports multiple database configurations:

#### MySQL (Recommended for Production)
```env
DATABASE_URL=mysql+pymysql://username:password@db:3306/smartvault
```

#### SQLite (Development Only)
```env
DATABASE_URL=sqlite:///./smartvault.db
```

### Redis Configuration

```env
# Default Redis (Docker)
REDIS_URL=redis://redis:6379

# Redis with password
REDIS_URL=redis://:password@redis:6379

# Redis with database selection
REDIS_URL=redis://redis:6379/1
```

### Security Settings

```env
# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-minimum-32-characters
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS Settings (configure for production)
CORS_ORIGINS=["http://localhost:3000", "https://yourdomain.com"]
```

## 🗄️ Database Setup

### Initial Database Setup

1. **Access the container**
   ```bash
   docker-compose exec api bash
   ```

2. **Initialize the database**
   ```bash
   # For new installations
   alembic upgrade head

   # For existing databases with schema changes
   alembic revision --autogenerate -m "Update schema"
   alembic upgrade head
   ```

3. **Verify database connection**
   ```bash
   # Test database connectivity
   python -c "from app.core.database import engine; print('Database connected successfully')"
   ```

### Database Migrations

#### Creating New Migrations
```bash
# Generate migration from model changes
alembic revision --autogenerate -m "Add new field to User model"

# Review the generated migration file
# Edit if necessary, then apply
alembic upgrade head
```

#### Rolling Back Migrations
```bash
# Check current revision
alembic current

# Rollback one revision
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

## 💻 Development Workflow

### Development with Docker

1. **Start services in development mode**
   ```bash
   docker-compose up -d
   ```

2. **View application logs**
   ```bash
   docker-compose logs -f api
   ```

3. **Make code changes**
   - Edit files in your host machine
   - Changes are reflected immediately due to volume mounting

4. **Restart services after dependency changes**
   ```bash
   docker-compose restart api
   ```

### Adding New Dependencies

1. **Update requirements.txt**
   ```bash
   # Add new dependencies
   echo "new-package==1.0.0" >> requirements.txt
   ```

2. **Rebuild the container**
   ```bash
   docker-compose build --no-cache api
   docker-compose up -d api
   ```

### Database Development

```bash
# Access database directly
docker-compose exec db mysql -u root -p smartvault

# Run migrations during development
docker-compose exec api alembic revision --autogenerate -m "Development changes"
docker-compose exec api alembic upgrade head
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Port Conflicts
```bash
# Check what's using port 8000
netstat -tulpn | grep :8000

# Or use different ports
docker-compose up -d -p 8001:8001
```

#### 2. Database Connection Issues
```bash
# Check database container logs
docker-compose logs db

# Test database connectivity
docker-compose exec api python -c "from app.core.database import engine; engine.connect(); print('OK')"
```

#### 3. Redis Connection Issues
```bash
# Check Redis container
docker-compose logs redis

# Test Redis connection
docker-compose exec api python -c "import redis; r = redis.Redis(host='redis', port=6379); print(r.ping())"
```

#### 4. Permission Issues
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
sudo chmod -R 755 .
```

#### 5. Container Won't Start
```bash
# Check detailed logs
docker-compose logs api

# Rebuild container
docker-compose down
docker-compose build --no-cache api
docker-compose up -d api
```

### Debug Mode

Enable debug logging by setting in `.env`:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Health Checks

```bash
# Check container health
docker-compose ps

# Application health endpoint
curl http://localhost:8000/health

# Database health
docker-compose exec api python -c "from app.core.database import engine; print(engine.execute('SELECT 1').fetchone())"
```

## 🚀 Production Considerations

### Security Checklist

- [ ] Change default JWT secret
- [ ] Configure CORS properly
- [ ] Use strong database passwords
- [ ] Enable HTTPS
- [ ] Set up proper logging
- [ ] Configure rate limiting
- [ ] Set up monitoring and alerts

### Production Docker Compose

Create a `docker-compose.prod.yml`:

```yaml
version: "3.9"
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.prod
    environment:
      - ENVIRONMENT=production
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass yourpassword
    restart: unless-stopped

  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: your-strong-password
      MYSQL_DATABASE: smartvault
    volumes:
      - mysql_data:/var/lib/mysql
    restart: unless-stopped
```

### Environment Variables for Production

```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
JWT_SECRET=your-production-secret-key
DATABASE_URL=mysql+pymysql://user:pass@db:3306/smartvault
REDIS_URL=redis://:password@redis:6379
CORS_ORIGINS=["https://yourdomain.com"]
```

### Backup Strategy

```bash
# Database backup
docker-compose exec db mysqldump -u root -p smartvault > backup.sql

# Redis backup
docker-compose exec redis redis-cli SAVE
docker cp smartvault-redis:/data/dump.rdb ./backup/redis-$(date +%Y%m%d).rdb
```

## 💡 Expert Recommendations

### Architecture Best Practices

**Container Optimization**
- Use multi-stage Docker builds to reduce image size
- Implement health checks for all services
- Use specific Redis and database versions instead of "latest" tags
- Consider using Docker secrets for sensitive environment variables

**Service Architecture**
- Separate read and write databases for better performance
- Implement Redis clustering for high availability
- Use a reverse proxy (nginx) for production deployments
- Consider API versioning strategy early in development

### Security Enhancements

**Authentication & Authorization**
- Implement rate limiting on all endpoints
- Use Redis for distributed session storage
- Add API key authentication for internal services
- Implement proper password policies and complexity requirements

**Network Security**
- Use internal Docker networks for service communication
- Implement firewall rules to restrict container access
- Enable TLS/SSL for all external communications
- Regular security updates for base images

### Performance Optimization

**Database Performance**
- Implement connection pooling for database connections
- Use Redis for caching frequently accessed data
- Optimize SQL queries and add appropriate indexes
- Consider read replicas for heavy read workloads

**Application Performance**
- Implement asynchronous processing for heavy operations
- Use background tasks for non-critical operations
- Add caching layers for API responses
- Monitor and optimize WebSocket connections

### Development Workflow

**Code Quality**
- Implement comprehensive test coverage (unit, integration, e2e)
- Use pre-commit hooks for code quality checks
- Implement continuous integration/continuous deployment (CI/CD)
- Regular code reviews and pair programming

**Environment Management**
- Use different Docker Compose files for each environment
- Implement environment-specific configurations
- Use Docker secrets or external secret management
- Document all environment variables and their purposes

### Monitoring & Observability

**Logging Strategy**
- Implement structured logging with correlation IDs
- Use centralized logging solutions (ELK stack, etc.)
- Monitor application metrics and set up alerts
- Log security events and access patterns

**Health Monitoring**
- Implement comprehensive health checks
- Monitor resource usage (CPU, memory, disk)
- Set up alerts for service failures
- Track API performance metrics

### Scalability Considerations

**Horizontal Scaling**
- Design stateless application components
- Implement load balancing for API services
- Use Redis clustering for session management
- Consider microservices architecture for complex features

**Data Management**
- Implement database backup and recovery strategies
- Use data replication for high availability
- Consider data archiving strategies for log data
- Implement data retention policies

### Maintenance & Operations

**Regular Maintenance**
- Schedule regular dependency updates
- Perform security audits and penetration testing
- Monitor and update SSL certificates
- Regular backup testing and validation

**Disaster Recovery**
- Implement automated backup strategies
- Test disaster recovery procedures regularly
- Document incident response procedures
- Plan for service downtime and maintenance windows

### Team Collaboration

**Documentation**
- Maintain up-to-date API documentation
- Document deployment and troubleshooting procedures
- Create runbooks for common operational tasks
- Keep architecture decision records (ADRs)

**Development Practices**
- Use feature branches and pull requests
- Implement code review processes
- Regular team knowledge sharing sessions
- Cross-training on different system components

---

*These recommendations are based on industry best practices and can be implemented incrementally as your project grows. Start with security and monitoring foundations, then focus on performance and scalability optimizations.*
## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Docker Documentation](https://docs.docker.com/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Need Help?**

- Check the troubleshooting section above
- Review the application logs: `docker-compose logs -f api`
- Ensure all environment variables are set correctly
- Verify database and Redis connections are working

For additional support, please refer to the project documentation or create an issue in the repository.