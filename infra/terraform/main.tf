terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID. From: az account show --query id --output tsv"
}

variable "location" {
  type        = string
  description = "Region for the new registry, log workspace, and Container Apps environment."
  default     = "eastus"
}

variable "resource_group_name" {
  type        = string
  description = "Existing resource group. This account cannot create resource groups."
  default     = "rg-josephat-oyondi"
}

variable "name_suffix" {
  type        = string
  description = "3-10 lowercase letters or numbers. Keeps the registry and app names unique."

  validation {
    condition     = can(regex("^[a-z0-9]{3,10}$", var.name_suffix))
    error_message = "name_suffix must be 3-10 lowercase letters or numbers."
  }
}

variable "key_vault_name" {
  type        = string
  description = "Existing vault that already holds the OpenAI, Search, Cosmos, and App Insights secrets."
  default     = "clinic-kv-tc-training"
}

variable "key_vault_resource_group_name" {
  type        = string
  description = "Resource group of the existing Key Vault."
  default     = "rg-josephat-oyondi"
}

variable "redis_url" {
  type        = string
  description = "Azure Managed Redis host:port. No password. The app signs in with its managed identity."
  default     = "redis-db-rs.eastus.redis.azure.net:10000"
}

variable "search_endpoint" {
  type        = string
  description = "Existing Azure AI Search endpoint. The admin key stays in Key Vault."
  default     = "https://clinic-training-ss.search.windows.net"
}

variable "image_tag" {
  type        = string
  description = "Tag pushed by az acr build before the container app is created."
  default     = "latest"
}

data "azurerm_client_config" "current" {}

data "azurerm_key_vault" "clinic" {
  name                = var.key_vault_name
  resource_group_name = var.key_vault_resource_group_name
}

resource "azurerm_container_registry" "main" {
  name                = "acrloan${var.name_suffix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = true
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-loan-${var.name_suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-loan-${var.name_suffix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

resource "azurerm_container_app" "api" {
  name                         = "ca-loan-${var.name_suffix}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "loan-copilot"
      image  = "${azurerm_container_registry.main.login_server}/loan-copilot:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "USE_KEY_VAULT"
        value = "true"
      }
      env {
        name  = "KEY_VAULT_NAME"
        value = var.key_vault_name
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = "gpt-6.1-terra"
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_MINI"
        value = "gpt-6.1-terra"
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_EMBEDDING"
        value = "text-embedding-3-small"
      }
      env {
        name  = "REDIS_URL"
        value = var.redis_url
      }
      env {
        name  = "USE_COSMOS"
        value = "true"
      }
      env {
        name  = "COSMOS_DATABASE"
        value = "loan_underwriting"
      }
      env {
        name  = "COSMOS_CONTAINER_CUSTOMERS"
        value = "customers"
      }
      env {
        name  = "USE_AZURE_SEARCH"
        value = "true"
      }
      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = var.search_endpoint
      }
      env {
        name  = "AZURE_SEARCH_INDEX_POLICIES"
        value = "loan-policy-memory"
      }
      env {
        name  = "AZURE_SEARCH_INDEX_PRECEDENTS"
        value = "loan-case-precedents"
      }
      env {
        name  = "LANGSMITH_TRACING"
        value = "false"
      }

      liveness_probe {
        transport        = "HTTP"
        port             = 8080
        path             = "/health"
        initial_delay    = 15
        interval_seconds = 30
      }
    }
  }
}

# The vault uses access policies. A role assignment is not used here because
# this account cannot create role assignments in the subscription.
resource "azurerm_key_vault_access_policy" "app" {
  key_vault_id = data.azurerm_key_vault.clinic.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_container_app.api.identity[0].principal_id

  secret_permissions = ["Get", "List"]
}

output "registry_name" {
  value = azurerm_container_registry.main.name
}

output "registry_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "container_app_url" {
  value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "container_app_principal_id" {
  value = azurerm_container_app.api.identity[0].principal_id
}

output "container_app_environment_name" {
  value = azurerm_container_app_environment.main.name
}
