# SimForge production IaC (blueprint §A.4, §J.3). SCAFFOLDING — review + `terraform init`
# against a real AWS account before applying. Not applied in dev.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # backend "s3" { bucket = "simforge-tfstate" key = "prod/terraform.tfstate" region = "us-west-2" }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "env" {
  type    = string
  default = "prod"
}

locals {
  name = "simforge-${var.env}"
  tags = {
    Project = "simforge"
    Env     = var.env
  }
}
