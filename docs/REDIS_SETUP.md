# Redis Setup Guide for AVI

This guide covers Redis configuration for AVI's caching system in production environments.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation Options](#installation-options)
- [Configuration](#configuration)
- [High Availability (Sentinel)](#high-availability-sentinel)
- [Horizontal Scaling (Cluster)](#horizontal-scaling-cluster)
- [Connection Strings](#connection-strings)
- [Performance Tuning](#performance-tuning)
- [Security Best Practices](#security-best-practices)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

AVI uses Redis as an optional distributed cache backend for:

- **Response Caching**: Store LLM responses and RAG results to reduce latency and API costs
- **Filter Rule Caching**: Cache vector search results for content filtering
- **Session Management**: Track user sessions across multiple API instances
- **Rate Limiting**: Coordinate rate limits across distributed deployments (future)

Redis is **optional** for development but **recommended** for production deployments with multiple API instances.

### When to Use Redis

| Scenario | Recommendation |
|----------|----------------|
| Single instance, development | ✗ Use in-memory cache (default) |
| Single instance, production | ✓ Optional (for persistence across restarts) |
| Multi-instance deployment | ✓✓ **Required** (shared cache) |
| High availability setup | ✓✓ **Required** with Sentinel/Cluster |

## Quick Start

### Docker Compose (Recommended for Development)

Add Redis to your existing `docker-compose.yml`:

```yaml
version: '3.8'

services:
  avi-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CACHE_BACKEND=redis
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  redis_data:
```

Update your `.env`:

```bash
CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

Start the services:

```bash
docker-compose up -d
```

## Installation Options

### Option 1: Docker (Recommended)

**Single Instance**:
```bash
docker run -d \
  --name avi-redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

**With Password Protection**:
```bash
docker run -d \
  --name avi-redis \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes --requirepass "your_secure_password"
```

### Option 2: Local Installation

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

**macOS (Homebrew)**:
```bash
brew install redis
brew services start redis
```

**RHEL/CentOS**:
```bash
sudo yum install redis
sudo systemctl enable redis
sudo systemctl start redis
```

### Option 3: Managed Cloud Services

**AWS ElastiCache**:
- Fully managed Redis service
- Automatic failover and backups
- Multi-AZ replication
- Connection string format: `redis://primary-endpoint:6379`

**Azure Cache for Redis**:
- Enterprise-grade Redis service
- Built-in high availability
- Connection string format: `redis://:password@cache-name.redis.cache.windows.net:6380?ssl=true`

**Google Cloud Memorystore**:
- Fully managed Redis instances
- VPC-native networking
- Connection string format: `redis://instance-ip:6379`

**Redis Cloud** (Redis Labs):
- Official managed service
- Free tier available
- Global deployments
- Connection string provided in dashboard

## Configuration

### Environment Variables

AVI supports two configuration methods:

**Method 1: Full Connection URL** (Recommended)
```bash
CACHE_BACKEND=redis
REDIS_URL=redis://username:password@host:6379/0
```

**Method 2: Individual Parameters**
```bash
CACHE_BACKEND=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_USERNAME=default
REDIS_PASSWORD=your_password
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CACHE_BACKEND` | `memory` | Set to `redis` to enable Redis cache |
| `CACHE_TTL` | `3600` | Cache entry TTL in seconds (1 hour) |
| `CACHE_MAX_SIZE` | `10000` | Max items (used for memory fallback) |
| `REDIS_URL` | - | Full Redis connection URL (overrides individual params) |
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_DB` | `0` | Redis database number (0-15) |
| `REDIS_USERNAME` | - | Redis ACL username (Redis 6+) |
| `REDIS_PASSWORD` | - | Redis password |

### Cache Key Naming

AVI uses the following key prefix format:

```
{APP_NAME}-cache:{key}
```

Example keys:
```
avi-poc-cache:query_response_abc123
avi-poc-cache:filter_rule_xyz789
avi-poc-cache:__keys__
```

The `__keys__` set tracks all cached keys for efficient clearing and statistics.

## High Availability (Sentinel)

Redis Sentinel provides automatic failover and monitoring for production deployments.

### Architecture

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Redis     │◄─────►│   Redis     │◄─────►│   Redis     │
│  Primary    │       │  Replica 1  │       │  Replica 2  │
└─────────────┘       └─────────────┘       └─────────────┘
       ▲                     ▲                     ▲
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
                   ┌─────────┴─────────┐
                   │  Sentinel Cluster │
                   │   (3+ instances)  │
                   └───────────────────┘
```

### Docker Compose with Sentinel

```yaml
version: '3.8'

services:
  redis-primary:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_primary:/data

  redis-replica-1:
    image: redis:7-alpine
    command: redis-server --replicaof redis-primary 6379 --appendonly yes
    depends_on:
      - redis-primary

  redis-replica-2:
    image: redis:7-alpine
    command: redis-server --replicaof redis-primary 6379 --appendonly yes
    depends_on:
      - redis-primary

  sentinel-1:
    image: redis:7-alpine
    command: >
      sh -c "echo 'sentinel monitor mymaster redis-primary 6379 2
      sentinel down-after-milliseconds mymaster 5000
      sentinel parallel-syncs mymaster 1
      sentinel failover-timeout mymaster 10000' > /tmp/sentinel.conf &&
      redis-sentinel /tmp/sentinel.conf"
    depends_on:
      - redis-primary

  sentinel-2:
    image: redis:7-alpine
    command: >
      sh -c "echo 'sentinel monitor mymaster redis-primary 6379 2
      sentinel down-after-milliseconds mymaster 5000
      sentinel parallel-syncs mymaster 1
      sentinel failover-timeout mymaster 10000' > /tmp/sentinel.conf &&
      redis-sentinel /tmp/sentinel.conf"
    depends_on:
      - redis-primary

  sentinel-3:
    image: redis:7-alpine
    command: >
      sh -c "echo 'sentinel monitor mymaster redis-primary 6379 2
      sentinel down-after-milliseconds mymaster 5000
      sentinel parallel-syncs mymaster 1
      sentinel failover-timeout mymaster 10000' > /tmp/sentinel.conf &&
      redis-sentinel /tmp/sentinel.conf"
    depends_on:
      - redis-primary

  avi-api:
    build: .
    environment:
      - CACHE_BACKEND=redis
      - REDIS_URL=redis://redis-primary:6379/0
    depends_on:
      - sentinel-1
      - sentinel-2
      - sentinel-3

volumes:
  redis_primary:
```

### Sentinel Configuration

For production Sentinel setup, create `sentinel.conf`:

```conf
# Monitor primary instance
sentinel monitor mymaster <primary-ip> 6379 2

# Number of milliseconds before declaring instance down
sentinel down-after-milliseconds mymaster 5000

# How many replicas can sync with new primary simultaneously
sentinel parallel-syncs mymaster 1

# Failover timeout
sentinel failover-timeout mymaster 10000

# Notification scripts (optional)
# sentinel notification-script mymaster /path/to/notify.sh
# sentinel client-reconfig-script mymaster /path/to/reconfig.sh
```

Start Sentinel:
```bash
redis-sentinel /path/to/sentinel.conf
```

### Connecting to Sentinel

Update your AVI configuration to use Sentinel endpoints:

```bash
CACHE_BACKEND=redis
REDIS_URL=redis+sentinel://sentinel1:26379,sentinel2:26379,sentinel3:26379/mymaster
```

**Note**: The redis-py library (used by AVI) supports Sentinel through `RedisSentinel` class. For full Sentinel support, you may need to extend `RedisCacheSystem._create_client()` in `src/core/cache_system.py`.

## Horizontal Scaling (Cluster)

Redis Cluster provides automatic sharding across multiple nodes for large-scale deployments.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Redis Cluster                       │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Primary  │  │ Primary  │  │ Primary  │         │
│  │  Node 1  │  │  Node 2  │  │  Node 3  │         │
│  │ [0-5460] │  │[5461-    │  │[10923-   │         │
│  │          │  │  10922]  │  │  16383]  │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │                 │
│  ┌────▼─────┐  ┌───▼──────┐  ┌───▼──────┐         │
│  │ Replica  │  │ Replica  │  │ Replica  │         │
│  │  Node 1  │  │  Node 2  │  │  Node 3  │         │
│  └──────────┘  └──────────┘  └──────────┘         │
└─────────────────────────────────────────────────────┘
```

### Docker Compose with Cluster

```yaml
version: '3.8'

services:
  redis-node-1:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes --port 7001
    ports:
      - "7001:7001"

  redis-node-2:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes --port 7002
    ports:
      - "7002:7002"

  redis-node-3:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes --port 7003
    ports:
      - "7003:7003"

  redis-node-4:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes --port 7004
    ports:
      - "7004:7004"

  redis-node-5:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes --port 7005
    ports:
      - "7005:7005"

  redis-node-6:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes --port 7006
    ports:
      - "7006:7006"

  redis-cluster-init:
    image: redis:7-alpine
    depends_on:
      - redis-node-1
      - redis-node-2
      - redis-node-3
      - redis-node-4
      - redis-node-5
      - redis-node-6
    command: >
      sh -c "sleep 5 && redis-cli --cluster create
      redis-node-1:7001 redis-node-2:7002 redis-node-3:7003
      redis-node-4:7004 redis-node-5:7005 redis-node-6:7006
      --cluster-replicas 1 --cluster-yes"
```

### Cluster Configuration

For manual cluster setup:

1. **Start cluster-enabled nodes**:
```bash
redis-server --cluster-enabled yes \
  --cluster-config-file nodes.conf \
  --cluster-node-timeout 5000 \
  --appendonly yes \
  --port 7001
```

2. **Create cluster**:
```bash
redis-cli --cluster create \
  host1:7001 host2:7002 host3:7003 \
  host4:7004 host5:7005 host6:7006 \
  --cluster-replicas 1
```

3. **Verify cluster**:
```bash
redis-cli -c -p 7001 cluster info
redis-cli -c -p 7001 cluster nodes
```

### Connecting to Cluster

Update AVI configuration:

```bash
CACHE_BACKEND=redis
REDIS_URL=redis://node1:7001,node2:7002,node3:7003/?cluster=true
```

**Note**: Full Redis Cluster support requires the `redis-py-cluster` library or redis-py 4.0+ with cluster support. You may need to extend `RedisCacheSystem` implementation in `src/core/cache_system.py`.

## Connection Strings

### Format Examples

**Basic connection**:
```
redis://localhost:6379
redis://localhost:6379/0
```

**With authentication**:
```
redis://:password@localhost:6379
redis://username:password@localhost:6379/0
```

**SSL/TLS connection**:
```
rediss://localhost:6380
rediss://:password@localhost:6380/0?ssl_cert_reqs=required
```

**Unix socket**:
```
unix:///var/run/redis/redis.sock
unix:///var/run/redis/redis.sock?db=0
```

**AWS ElastiCache**:
```
redis://primary.abcdef.cache.amazonaws.com:6379
```

**Azure Cache for Redis**:
```
rediss://:password@mycache.redis.cache.windows.net:6380?ssl=true
```

**Redis Cloud**:
```
redis://:password@redis-12345.c123.region.cloud.redislabs.com:12345
```

### Connection Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `db` | Database number (0-15) | `?db=1` |
| `ssl` | Enable SSL/TLS | `?ssl=true` |
| `ssl_cert_reqs` | SSL certificate verification | `?ssl_cert_reqs=required` |
| `socket_timeout` | Socket timeout in seconds | `?socket_timeout=5` |
| `socket_connect_timeout` | Connection timeout | `?socket_connect_timeout=5` |
| `socket_keepalive` | Enable TCP keepalive | `?socket_keepalive=true` |
| `health_check_interval` | Health check interval | `?health_check_interval=30` |

## Performance Tuning

### Memory Management

**Set maximum memory limit**:
```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

**Eviction policies**:
- `allkeys-lru`: Evict any key using LRU (recommended for cache)
- `volatile-lru`: Evict keys with TTL using LRU
- `allkeys-lfu`: Evict any key using LFU (Redis 4.0+)
- `volatile-lfu`: Evict keys with TTL using LFU
- `allkeys-random`: Evict random keys
- `volatile-random`: Evict random keys with TTL
- `volatile-ttl`: Evict keys with shortest TTL
- `noeviction`: Return errors when memory limit reached (not recommended)

### Persistence Configuration

**RDB (snapshot) persistence**:
```bash
# redis.conf
save 900 1      # Save after 900s if >= 1 key changed
save 300 10     # Save after 300s if >= 10 keys changed
save 60 10000   # Save after 60s if >= 10000 keys changed

dbfilename dump.rdb
dir /var/lib/redis
```

**AOF (append-only file) persistence**:
```bash
# redis.conf
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec  # Options: always, everysec, no

# AOF rewrite configuration
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

**Hybrid persistence** (recommended for production):
```bash
# Enable both RDB and AOF
save 900 1
appendonly yes
appendfsync everysec
```

### Network Optimization

**TCP settings**:
```bash
# redis.conf
tcp-backlog 511
tcp-keepalive 300
timeout 0  # 0 = never close idle connections

# Disable slow commands in production
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

### AVI-Specific Tuning

**Recommended settings for AVI cache workload**:

```bash
# In .env
CACHE_TTL=3600          # 1 hour (adjust based on your needs)
CACHE_MAX_SIZE=10000    # Fallback size for in-memory

# In redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
save 900 1
save 300 10
```

**For high-traffic deployments**:
```bash
# In .env
CACHE_TTL=7200          # 2 hours
CACHE_MAX_SIZE=50000

# In redis.conf
maxmemory 8gb
maxmemory-policy allkeys-lfu  # LFU for better hit rate
```

## Security Best Practices

### Authentication

**Enable password authentication**:
```bash
# redis.conf
requirepass your_strong_password_here
```

**Use ACL (Redis 6+)** for fine-grained access control:
```bash
# redis.conf
aclfile /etc/redis/users.acl
```

Example ACL file:
```
user default on nopass ~* &* +@all
user avi_cache on >secure_password ~avi-poc-cache:* +get +set +setex +del +exists +ttl +smembers +sadd +srem +scard +ping
```

Configure AVI to use ACL user:
```bash
REDIS_USERNAME=avi_cache
REDIS_PASSWORD=secure_password
```

### Network Security

**Bind to specific interfaces**:
```bash
# redis.conf
bind 127.0.0.1 ::1          # Local only
bind 10.0.1.5 ::1           # Private network only
bind 0.0.0.0 ::0            # All interfaces (use with firewall!)
```

**Use SSL/TLS** (Redis 6+):
```bash
# redis.conf
port 0                      # Disable unencrypted port
tls-port 6380
tls-cert-file /path/to/redis.crt
tls-key-file /path/to/redis.key
tls-ca-cert-file /path/to/ca.crt
```

Configure AVI:
```bash
REDIS_URL=rediss://localhost:6380/0?ssl_cert_reqs=required
```

### Firewall Rules

**Allow only AVI servers**:
```bash
# iptables
iptables -A INPUT -p tcp --dport 6379 -s 10.0.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 6379 -j DROP

# ufw
ufw allow from 10.0.1.0/24 to any port 6379
ufw deny 6379
```

### Docker Security

**Run Redis as non-root**:
```yaml
services:
  redis:
    image: redis:7-alpine
    user: "999:999"  # Redis user UID:GID
    command: redis-server --appendonly yes --requirepass "${REDIS_PASSWORD}"
```

**Use Docker secrets**:
```yaml
services:
  redis:
    image: redis:7-alpine
    secrets:
      - redis_password
    command: sh -c 'redis-server --requirepass "$$(cat /run/secrets/redis_password)"'

secrets:
  redis_password:
    file: ./secrets/redis_password.txt
```

## Monitoring

### Health Checks

**Basic ping check**:
```bash
redis-cli ping
# Expected: PONG
```

**Check memory usage**:
```bash
redis-cli INFO memory
```

**Check connected clients**:
```bash
redis-cli CLIENT LIST
```

**Monitor commands in real-time**:
```bash
redis-cli MONITOR
```

### Key Metrics to Track

| Metric | Command | Threshold |
|--------|---------|-----------|
| Memory usage | `INFO memory` | < 80% of maxmemory |
| Evicted keys | `INFO stats` (evicted_keys) | Low rate |
| Keyspace hits/misses | `INFO stats` | Hit rate > 80% |
| Connected clients | `INFO clients` | Monitor trends |
| Commands/sec | `INFO stats` | Monitor trends |
| Replication lag | `INFO replication` | < 1 second |

### Prometheus Integration

AVI exposes Prometheus metrics at `/metrics` endpoint, including cache statistics:

```
# HELP avi_cache_hits_total Total number of cache hits
# TYPE avi_cache_hits_total counter
avi_cache_hits_total{backend="redis"} 15423

# HELP avi_cache_misses_total Total number of cache misses
# TYPE avi_cache_misses_total counter
avi_cache_misses_total{backend="redis"} 3521

# HELP avi_cache_size Current number of items in cache
# TYPE avi_cache_size gauge
avi_cache_size{backend="redis"} 8743
```

### Grafana Dashboard

Example queries for Redis monitoring:

```promql
# Cache hit rate
rate(avi_cache_hits_total{backend="redis"}[5m]) /
(rate(avi_cache_hits_total{backend="redis"}[5m]) + rate(avi_cache_misses_total{backend="redis"}[5m])) * 100

# Cache size
avi_cache_size{backend="redis"}

# Redis memory usage (requires redis_exporter)
redis_memory_used_bytes / redis_memory_max_bytes * 100
```

### Redis Exporter

For detailed Redis metrics, use [redis_exporter](https://github.com/oliver006/redis_exporter):

```yaml
services:
  redis-exporter:
    image: oliver006/redis_exporter:latest
    ports:
      - "9121:9121"
    environment:
      - REDIS_ADDR=redis://redis:6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      - redis
```

## Troubleshooting

### Common Issues

#### 1. Connection Refused

**Symptom**: `ConnectionRefusedError` or `Error 111 connecting to localhost:6379`

**Causes**:
- Redis not running
- Wrong host/port
- Firewall blocking connection

**Solutions**:
```bash
# Check if Redis is running
redis-cli ping

# Check Redis status
systemctl status redis
docker ps | grep redis

# Check if port is open
netstat -tlnp | grep 6379
lsof -i :6379

# Test connection
telnet localhost 6379

# Check firewall
sudo iptables -L -n | grep 6379
sudo ufw status
```

#### 2. Authentication Failed

**Symptom**: `NOAUTH Authentication required` or `invalid password`

**Solutions**:
```bash
# Verify password in config
redis-cli -a your_password ping

# Check .env configuration
grep REDIS_PASSWORD .env

# Verify Redis requirepass setting
redis-cli CONFIG GET requirepass
```

#### 3. Out of Memory

**Symptom**: `OOM command not allowed when used memory > 'maxmemory'`

**Solutions**:
```bash
# Check memory usage
redis-cli INFO memory | grep used_memory_human

# Check maxmemory setting
redis-cli CONFIG GET maxmemory

# Increase maxmemory
redis-cli CONFIG SET maxmemory 2gb

# Set eviction policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Clear cache manually
redis-cli FLUSHDB  # Caution: removes all data!
```

#### 4. AVI Falls Back to In-Memory Cache

**Symptom**: Logs show "Falling back to in-memory cache"

**Causes**:
- Redis not reachable
- redis-py not installed
- Configuration error

**Solutions**:
```bash
# Check redis-py installation
pip show redis

# Install if missing
pip install redis>=4.0.0

# Verify configuration
python3 -c "from config.settings import settings; print(f'Backend: {settings.CACHE_BACKEND}'); print(f'Redis URL: {settings.REDIS_URL}')"

# Test connection from Python
python3 -c "from redis import Redis; r = Redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

#### 5. Slow Response Times

**Symptoms**: High latency, slow cache operations

**Diagnostic**:
```bash
# Check slow log
redis-cli SLOWLOG GET 10

# Monitor commands
redis-cli --latency
redis-cli --latency-history

# Check if disk I/O is blocking
redis-cli INFO persistence | grep loading
```

**Solutions**:
- Reduce `appendfsync` frequency (everysec instead of always)
- Disable persistence if acceptable for cache use case
- Use faster storage (SSD instead of HDD)
- Increase network bandwidth

#### 6. High Memory Fragmentation

**Symptom**: `mem_fragmentation_ratio` > 1.5

**Diagnostic**:
```bash
redis-cli INFO memory | grep fragmentation
```

**Solution**:
```bash
# Active defragmentation (Redis 4.0+)
redis-cli CONFIG SET activedefrag yes

# Or restart Redis during maintenance window
systemctl restart redis
```

#### 7. Replication Lag

**Symptom**: Replica behind primary, data inconsistency

**Diagnostic**:
```bash
# Check replication status
redis-cli INFO replication

# Check replication offset
redis-cli -h replica INFO replication | grep master_repl_offset
redis-cli -h primary INFO replication | grep master_repl_offset
```

**Solutions**:
- Check network latency between primary and replica
- Reduce write load on primary
- Increase `repl-backlog-size` in redis.conf
- Use faster storage on replica

### Debug Mode

Enable debug logging in AVI to troubleshoot cache issues:

```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG
```

Check logs:
```bash
# Docker
docker-compose logs -f avi-api | grep -i redis

# Local
tail -f logs/avi.log | grep -i redis
```

### Testing Redis Connection

**Test script** (`test_redis.py`):
```python
#!/usr/bin/env python3
import sys
from redis import Redis
from redis.exceptions import RedisError

def test_redis_connection(url: str):
    try:
        client = Redis.from_url(url, decode_responses=True)

        # Test PING
        print(f"✓ Connected to Redis: {client.ping()}")

        # Test SET/GET
        client.set("avi_test", "hello")
        value = client.get("avi_test")
        assert value == "hello", f"Expected 'hello', got '{value}'"
        print(f"✓ SET/GET working")

        # Test TTL
        client.setex("avi_test_ttl", 60, "world")
        ttl = client.ttl("avi_test_ttl")
        assert 50 < ttl <= 60, f"TTL not working correctly: {ttl}"
        print(f"✓ TTL working")

        # Cleanup
        client.delete("avi_test", "avi_test_ttl")

        # Get INFO
        info = client.info("server")
        print(f"✓ Redis version: {info['redis_version']}")

        memory = client.info("memory")
        print(f"✓ Memory used: {memory['used_memory_human']}")

        return True

    except RedisError as e:
        print(f"✗ Redis error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "redis://localhost:6379/0"
    success = test_redis_connection(url)
    sys.exit(0 if success else 1)
```

Run test:
```bash
python3 test_redis.py redis://localhost:6379/0
```

### Getting Help

If issues persist:

1. Check [Redis documentation](https://redis.io/documentation)
2. Review [redis-py documentation](https://redis-py.readthedocs.io/)
3. Search [Redis GitHub issues](https://github.com/redis/redis/issues)
4. Check AVI logs for detailed error messages
5. Enable DEBUG mode and reproduce the issue
6. Open an issue on AVI repository with:
   - Full error message and stack trace
   - AVI version and configuration (sanitize secrets!)
   - Redis version and configuration
   - Steps to reproduce

## Additional Resources

- [Redis Official Documentation](https://redis.io/documentation)
- [Redis Best Practices](https://redis.io/topics/best-practices)
- [Redis Security](https://redis.io/topics/security)
- [Redis Persistence](https://redis.io/topics/persistence)
- [Redis Replication](https://redis.io/topics/replication)
- [Redis Sentinel](https://redis.io/topics/sentinel)
- [Redis Cluster Tutorial](https://redis.io/topics/cluster-tutorial)
- [redis-py Documentation](https://redis-py.readthedocs.io/)
- [AWS ElastiCache Best Practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)

---

**Next Steps**: See [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) for comprehensive production deployment guidelines.
