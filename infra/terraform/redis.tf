# ElastiCache Redis cluster. Blueprint §J.3. SCAFFOLDING.
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"
  description          = "SimForge queue + PDP cache"
  engine               = "redis"
  node_type            = "cache.r6g.large"
  num_cache_clusters   = 2
  automatic_failover_enabled = true
  at_rest_encryption_enabled = true
  tags                 = local.tags
}
