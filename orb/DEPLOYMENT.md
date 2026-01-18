# Kagami Deployment Guide

Complete deployment documentation for Kagami AI Platform.

## Overview

Kagami is a production-ready AI platform that can be deployed in various environments:

- **Docker** - Containerized deployment for development and production
- **Kubernetes** - Scalable cloud-native deployment with Helm charts
- **Terraform** - Infrastructure as Code for AWS, GCP, and Azure
- **Bare Metal** - On-premise deployment with systemd services

## Quick Start

### Development (Docker Compose)

```bash
# Clone repository
git clone https://github.com/your-org/kagami.git
cd kagami

# Start all services
docker-compose up -d

# Check health
curl http://localhost:50794/health

# View logs
docker-compose logs -f api
```

### Production (Kubernetes + Helm)

```bash
# Add Helm repository
helm repo add kagami https://charts.kagami.ai
helm repo update

# Install with production values
helm install kagami kagami/kagami \
  --namespace kagami \
  --create-namespace \
  --values production-values.yaml

# Verify deployment
kubectl get pods -n kagami
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Load Balancer / Ingress                 │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Kagami API Cluster                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  API-1   │  │  API-2   │  │  API-3   │  │  API-N   │   │
│  │  (8001)  │  │  (8001)  │  │  (8001)  │  │  (8001)  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────┬─────────────────────────────┬───────────────────┘
            │                             │
            ▼                             ▼
┌─────────────────────┐     ┌─────────────────────────────────┐
│   CockroachDB       │     │         Redis Cluster           │
│   (Distributed SQL) │     │   (Cache + Session Store)       │
│   Port: 26257       │     │   Port: 6379                    │
└─────────────────────┘     └─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Support Services                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   etcd   │  │ Weaviate │  │Prometheus│  │ Grafana  │   │
│  │  (2379)  │  │  (8080)  │  │  (9090)  │  │  (3000)  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Hardware Requirements

**Minimum (Development)**
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB SSD
- Network: 100 Mbps

**Recommended (Production)**
- CPU: 8-16 cores
- RAM: 16-32 GB
- Disk: 200 GB NVMe SSD
- Network: 1 Gbps
- GPU (Optional): NVIDIA with 8GB+ VRAM for forge operations

### Software Requirements

- **Docker**: 24.0+ (for Docker/Docker Compose deployments)
- **Kubernetes**: 1.27+ (for K8s deployments)
- **Helm**: 3.12+ (for Helm deployments)
- **Terraform**: 1.5+ (for IaC deployments)
- **Python**: 3.11+ (for bare metal deployments)

### External Services

- **CockroachDB**: 23.1+ or PostgreSQL 15+
- **Redis**: 7.0+
- **etcd**: 3.5+
- **Weaviate**: 1.27+ (for RAG/vector search)

## Deployment Options

### 1. Docker Deployment

Best for: Development, small teams, single-server deployments

- **Guide**: [docs/deployment/docker.md](docs/deployment/docker.md)
- **Setup Time**: 15 minutes
- **Complexity**: Low
- **Scalability**: Limited (single node)

### 2. Kubernetes Deployment

Best for: Production, cloud environments, scalable workloads

- **Guide**: [docs/deployment/kubernetes.md](docs/deployment/kubernetes.md)
- **Setup Time**: 1-2 hours
- **Complexity**: Medium
- **Scalability**: High (horizontal scaling)

### 3. Terraform Deployment

Best for: Cloud infrastructure, multi-environment setups, IaC workflows

- **Guide**: [docs/deployment/terraform.md](docs/deployment/terraform.md)
- **Setup Time**: 2-4 hours
- **Complexity**: Medium-High
- **Scalability**: High (cloud provider dependent)

### 4. Bare Metal Deployment

Best for: On-premise, air-gapped environments, compliance requirements

- **Guide**: [docs/deployment/bare-metal.md](docs/deployment/bare-metal.md)
- **Setup Time**: 4-6 hours
- **Complexity**: High
- **Scalability**: Manual (horizontal requires load balancer)

## Configuration

Complete environment variable reference: [docs/deployment/configuration.md](docs/deployment/configuration.md)

### Essential Environment Variables

```bash
# Core Configuration
ENVIRONMENT=production
KAGAMI_BOOT_MODE=full
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:pass@host:26257/kagami?sslmode=require

# Redis
REDIS_URL=redis://user:pass@host:6379/0

# etcd (Distributed coordination)
ETCD_ENDPOINTS=http://etcd1:2379,http://etcd2:2379,http://etcd3:2379

# Weaviate (Vector database for RAG)
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_API_KEY=your-weaviate-api-key

# Security
JWT_SECRET=<generate-with-openssl-rand-hex-64>
KAGAMI_API_KEY=<generate-with-openssl-rand-hex-32>
SECRET_KEY=<generate-with-openssl-rand-hex-64>

# LLM Providers (choose one or more)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Production Checklist

Before deploying to production, complete this checklist: [docs/PRODUCTION_CHECKLIST.md](docs/PRODUCTION_CHECKLIST.md)

- [x] Security hardening complete (detect-secrets hook, Fernet encryption)
- [ ] TLS/SSL certificates configured
- [x] Secrets properly managed (keychain backend, env vars, no hardcoded values)
- [ ] Database backups configured
- [ ] Monitoring and alerting enabled
- [x] Resource limits configured (Docker Compose has memory/CPU limits)
- [ ] Disaster recovery plan documented
- [ ] Load testing completed
- [x] Security audit completed (Jan 2, 2026 - pre-mortem analysis)
- [x] Documentation updated (DEPLOYMENT.md, env.example)

## Monitoring

Set up comprehensive monitoring: [docs/deployment/monitoring.md](docs/deployment/monitoring.md)

- **Metrics**: Prometheus + Grafana
- **Logs**: Centralized log aggregation
- **Tracing**: OpenTelemetry (optional)
- **Alerts**: PagerDuty, Slack, email

### Quick Health Check

```bash
# API health
curl http://your-domain.com/health

# Detailed health with dependencies
curl http://your-domain.com/health/ready

# Metrics
curl http://your-domain.com/metrics
```

## Troubleshooting

Common issues and solutions: [docs/deployment/troubleshooting.md](docs/deployment/troubleshooting.md)

### Quick Diagnostics

```bash
# Check service status (Docker)
docker-compose ps

# View logs (Docker)
docker-compose logs -f api

# Check service status (Kubernetes)
kubectl get pods -n kagami
kubectl describe pod <pod-name> -n kagami
kubectl logs -f <pod-name> -n kagami

# Database connectivity
docker exec -it kagami-cockroachdb ./cockroach sql --insecure

# Redis connectivity
docker exec -it kagami-redis redis-cli ping
```

## Upgrading

Version upgrade procedures: [docs/deployment/upgrade-guide.md](docs/deployment/upgrade-guide.md)

### Zero-Downtime Upgrade (Kubernetes)

```bash
# Update Helm chart to new version
helm upgrade kagami kagami/kagami \
  --namespace kagami \
  --values production-values.yaml \
  --set image.tag=v2.1.0

# Monitor rollout
kubectl rollout status deployment/kagami -n kagami

# Rollback if needed
helm rollback kagami -n kagami
```

## Security

### Network Security

1. **Firewall Rules**: Only expose necessary ports
   - HTTP: 80 (redirects to HTTPS)
   - HTTPS: 443
   - Metrics: 9090 (internal only)

2. **TLS/SSL**: Always use TLS in production
   - Minimum TLS 1.3
   - Strong cipher suites
   - Valid certificates (Let's Encrypt recommended)

3. **Network Policies**: Restrict inter-service communication
   - Use Kubernetes NetworkPolicies
   - Implement zero-trust networking

### Authentication & Authorization

- **JWT tokens** for API authentication
- **API keys** for service-to-service communication
- **RBAC** for role-based access control
- **Rate limiting** to prevent abuse

### Secrets Management

- Use external secrets management (recommended):
  - AWS Secrets Manager
  - HashiCorp Vault
  - Kubernetes Secrets with encryption at rest
- Never commit secrets to version control
- Rotate secrets regularly (quarterly minimum)

## Performance Tuning

### Database Optimization

```sql
-- Connection pooling (recommended settings)
DB_POOL_SIZE=100
DB_MAX_OVERFLOW=100
DB_POOL_TIMEOUT=30

-- Query optimization
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_sessions_token ON sessions(token);
```

### Redis Optimization

```bash
# Memory limits
maxmemory 4gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
appendonly yes
```

### API Performance

```bash
# Worker processes (set to number of CPU cores)
WORKERS=8

# Connection limits
MAX_CONNECTIONS=1000
KEEPALIVE_TIMEOUT=65

# Request limits
MAX_REQUEST_SIZE=10485760  # 10MB
```

## Scaling

### Horizontal Scaling (Kubernetes)

```bash
# Manual scaling
kubectl scale deployment kagami --replicas=10 -n kagami

# Auto-scaling (HPA)
kubectl autoscale deployment kagami \
  --min=3 \
  --max=20 \
  --cpu-percent=70 \
  -n kagami
```

### Vertical Scaling

```yaml
# Increase resource limits
resources:
  limits:
    cpu: 4000m
    memory: 8Gi
  requests:
    cpu: 2000m
    memory: 4Gi
```

### Database Scaling

```bash
# CockroachDB horizontal scaling
# Add new nodes to the cluster
cockroach start --join=existing-node:26257
```

## Backup & Recovery

### Database Backups

```bash
# Automated daily backups
cockroach sql --execute="BACKUP TO 's3://bucket/backups/daily?AWS_ACCESS_KEY_ID=xxx&AWS_SECRET_ACCESS_KEY=yyy'"

# Restore from backup
cockroach sql --execute="RESTORE FROM 's3://bucket/backups/daily/2024-01-01'"
```

### Configuration Backups

```bash
# Backup Kubernetes resources
kubectl get all -n kagami -o yaml > kagami-backup.yaml

# Backup secrets
kubectl get secrets -n kagami -o yaml > kagami-secrets-backup.yaml
```

## Cost Optimization

### Cloud Costs

1. **Right-sizing**: Use appropriate instance types
   - Development: t3.medium (2 vCPU, 4 GB)
   - Production: c6i.2xlarge (8 vCPU, 16 GB)

2. **Reserved Instances**: 40-60% savings for predictable workloads

3. **Spot Instances**: Use for non-critical workloads (70-90% savings)

4. **Auto-scaling**: Scale down during off-peak hours

### Storage Costs

1. **Database**: Use tiered storage
   - Hot data: SSD (NVMe)
   - Cold data: Object storage (S3, GCS)

2. **Logs**: Retention policies
   - Application logs: 30 days
   - Audit logs: 365 days
   - Metrics: 90 days

## Support

### Community Support

- **Documentation**: https://docs.kagami.ai
- **GitHub Issues**: https://github.com/your-org/kagami/issues
- **Discord**: https://discord.gg/kagami

### Enterprise Support

- **Email**: support@kagami.ai
- **SLA**: 99.9% uptime guarantee
- **Response Time**: 1-hour for critical issues

## License

Kagami is available under multiple licenses:
- **Open Source**: Apache 2.0 (community features)
- **Enterprise**: Commercial license (advanced features, support)

See LICENSE file for details.

## Additional Resources

- [Docker Deployment Guide](docs/deployment/docker.md)
- [Kubernetes Deployment Guide](docs/deployment/kubernetes.md)
- [Terraform Deployment Guide](docs/deployment/terraform.md)
- [Bare Metal Deployment Guide](docs/deployment/bare-metal.md)
- [Production Checklist](docs/deployment/production-checklist.md)
- [Configuration Reference](docs/deployment/configuration.md)
- [Troubleshooting Guide](docs/deployment/troubleshooting.md)
- [Upgrade Guide](docs/deployment/upgrade-guide.md)
- [Monitoring Guide](docs/deployment/monitoring.md)
