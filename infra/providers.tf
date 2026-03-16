terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "martinme-dev-tfstate"
    key            = "martinme.dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "martinme-dev-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}
