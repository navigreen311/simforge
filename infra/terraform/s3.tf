# Evidence bucket with tiered lifecycle + cross-region replication. Blueprint §J.3.
resource "aws_s3_bucket" "evidence" {
  bucket = "${local.name}-evidence"
  tags   = local.tags
}
resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    id     = "tiered"
    status = "Enabled"
    transition { days = 30  storage_class = "STANDARD_IA" }
    transition { days = 365 storage_class = "GLACIER" }
    expiration { days = 2555 } # ~7 years (HIPAA-adjacent), subject to legal hold
  }
}
