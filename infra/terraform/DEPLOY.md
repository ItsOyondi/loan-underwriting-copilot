# Deploy the loan copilot as a container

`main.tf` builds the Docker image into a new Azure Container Registry and runs it as one Azure Container App. The image is the existing `Dockerfile` at the project root. It starts the FastAPI app on port 8080.

The container does not receive a `.env` file. `USE_KEY_VAULT=true` makes it read these existing secrets from `clinic-kv-tc-training` with its own managed identity:

| Setting left empty in the container | Key Vault secret |
|---|---|
| OpenAI endpoint and key | `az-openai-endpoint`, `az-openai-apikey` |
| Search admin key | `clinic-ss-api-key` |
| Cosmos endpoint and key | `cosmos-cxn-str`, `cosmos-cxn-key` |
| Application Insights | `app-insights-cxn-str` |

Redis, Cosmos, and Azure AI Search are the resources you already use. Terraform does not create or replace them. The tools stay in this one process. The five MCP servers are not separate containers.

| Resource | Name with suffix `loan01` | Created by this file |
|---|---|---|
| Resource group | `rg-josephat-oyondi` | no, it must already exist |
| Container Registry | `acrloanloan01` | yes, Basic, admin user on |
| Log Analytics workspace | `log-loan-loan01` | yes |
| Container Apps environment | `cae-loan-loan01` | yes |
| Container App | `ca-loan-loan01` | yes, external HTTPS, port 8080 |
| Key Vault access policy | get and list for the app identity | yes, on the existing vault |

The registry admin user is how the app pulls the image. This subscription's account cannot create role assignments, so the file does not grant `AcrPull`.

Run the commands yourself. Nothing below has been applied.

## 1. Install the tools

You need the [Terraform CLI](https://developer.hashicorp.com/terraform/install) and the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli). Docker Desktop is not required. `az acr build` builds the image in Azure.

```powershell
terraform version
az version
```

## 2. Sign in

```powershell
az login
az account set --subscription "AzureTraining"
az account show --query "{name:name, id:id}" --output table
```

Copy the subscription ID:

```powershell
az account show --query id --output tsv
```

## 3. Set the names

From `AzTraining/finUseCase`:

```powershell
cd AzTraining\finUseCase\infra\terraform
Copy-Item terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

- `subscription_id` — the ID from step 2.
- `name_suffix` — 3 to 10 lowercase letters or numbers. `loan01` produces registry `acrloanloan01`.
- Leave the Key Vault, Redis host, and Search endpoint unless those resources move.

Do not put API keys in this file. `terraform.tfvars` is gitignored.

## 4. Create the registry first

```powershell
terraform init
terraform fmt
terraform validate
terraform plan -target=azurerm_container_registry.main
terraform apply -target=azurerm_container_registry.main
```

`init` downloads the Azure provider. `validate` checks the file and does not call Azure. `apply -target` creates only the registry, because the container app cannot start until the image exists. Type `yes` when asked.

Read the registry name:

```powershell
terraform output -raw registry_name
```

## 5. Build and push the image

Run this from `AzTraining/finUseCase`, not from the `terraform` folder. The `.` is the Dockerfile directory.

```powershell
cd ..\..
az acr build --registry acrloanloan01 --image loan-copilot:latest .
```

Replace `acrloanloan01` with the output from step 4 if your suffix is different. The build runs in Azure and pushes `loan-copilot:latest` to that registry. Confirm it:

```powershell
az acr repository show --name acrloanloan01 --image loan-copilot:latest
```

## 6. Create the container app

```powershell
cd infra\terraform
terraform plan
terraform apply
```

The plan should add the Log Analytics workspace, the Container Apps environment, the container app, and one Key Vault access policy. It should not create a resource group, and it should not change Redis, Cosmos, Search, or OpenAI.

Type `yes`. The environment takes several minutes. When it finishes:

```powershell
terraform output container_app_url
terraform output container_app_principal_id
az containerapp env show --name cae-loan-loan01 --resource-group rg-josephat-oyondi --query "properties.outboundIpAddresses" --output tsv
```

## 7. Open Redis to the container

The app signs in to Redis with the container's managed identity, not with your user. Two things have to allow that identity.

1. In the Azure portal, open the Redis resource `redis-db-rs`. Under Authentication, Microsoft Entra Authentication, add the principal ID from `container_app_principal_id` the same way your user was added. Access is granted to that principal directly.
2. Under Networking, add a firewall rule for each address printed by the `outboundIpAddresses` command in step 6. Those are the addresses the container uses to leave Azure. A timeout on Redis means this list is missing. The app then keeps the audit trail in the container's local file, which disappears when the replica restarts.

Cosmos, Search, and OpenAI are reached with the keys from Key Vault. If one of those accounts has a firewall, add the same outbound IPs there too.

Restart the app after the policy and the firewall rule exist:

```powershell
az containerapp revision list --name ca-loan-loan01 --resource-group rg-josephat-oyondi --query "[].name" --output tsv
az containerapp revision restart --name ca-loan-loan01 --resource-group rg-josephat-oyondi --revision <name-from-the-list>
```

## 8. Call the API

Use the URL from `container_app_url`.

```powershell
curl https://<your-app-fqdn>/health
curl -X POST https://<your-app-fqdn>/cases -H "Content-Type: application/json" -d "{\"sample_case\":\"case_001_strong\",\"auto_approve\":true}"
```

`/health` returns `{"status":"ok",...}` when the process is up. The case call is the same request as the local API. It can take a few minutes because it calls Azure OpenAI. A Key Vault warning in the container logs means the access policy is missing or the identity was added after the replica started. Restart the revision from step 7.

Logs:

```powershell
az containerapp logs show --name ca-loan-loan01 --resource-group rg-josephat-oyondi --follow
```

Look for `Azure Monitor export is on`. Application Insights queries stay in `APP_INSIGHTS_QUERIES.md`.

## 9. Ship a new image later

From `AzTraining/finUseCase`:

```powershell
az acr build --registry acrloanloan01 --image loan-copilot:latest .
az containerapp update --name ca-loan-loan01 --resource-group rg-josephat-oyondi --image acrloanloan01.azurecr.io/loan-copilot:latest
```

## 10. Remove the deployment

From `infra/terraform`:

```powershell
terraform destroy
```

Type `yes`. This deletes the container app, the environment, the Log Analytics workspace, the registry and its images, and the app's Key Vault access policy. It leaves the resource group, the vault, Redis, Cosmos, Search, and OpenAI in place.

Do not commit `terraform.tfvars` or the `terraform.tfstate` files. The state contains the registry admin password.
