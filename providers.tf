terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region                   = var.aws_region
  access_key              = var.aws_access_key_id
  secret_key              = var.aws_secret_access_key
  endpoints {
    s3        = var.aws_endpoint_url
    kinesis   = var.aws_endpoint_url
    dynamodb  = var.aws_endpoint_url
    lambda    = var.aws_endpoint_url
    iam       = var.aws_endpoint_url
    events    = var.aws_endpoint_url
  }
  skip_credentials_validation = true
  skip_region_validation      = true
  skip_requesting_account_id  = true
}
