# Azure setup (free tier, from scratch)

One-time provisioning to make the `deploy.yml` workflow work end-to-end. Plan
on ~30 minutes the first time. All values in `<angle brackets>` are yours to
fill in.

## 0. Prerequisites

1. **Azure free account** — https://azure.microsoft.com/free/. Needs a credit
   card for identity verification; nothing in this scaffold should bill once
   provisioned correctly. The free grant gives $200 credit for 30 days plus 12
   months of free service quotas.
2. **Azure CLI** — https://learn.microsoft.com/cli/azure/install-azure-cli.
   On macOS: `brew install azure-cli`.
3. **GitHub repo** for this project, pushed to your account.

```bash
az login                 # opens browser
az account show          # confirm subscription
```

## 1. Variables (set once per shell session)

```bash
export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
export RESOURCE_GROUP=forest-cover-rg
export LOCATION=westeurope                 # pick a region near you
export CONTAINERAPP_ENV=forest-cover-env
export CONTAINERAPP_NAME=forest-cover-endpoint
export GITHUB_OWNER=<your-github-username>
export GITHUB_REPO=forest-cover-endpoint
```

## 2. Resource group + Container Apps environment

```bash
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

az extension add --name containerapp --upgrade

az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

az containerapp env create \
  --name "$CONTAINERAPP_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION"
```

## 3. First container app (placeholder image)

The first deploy uses a public placeholder so the resource exists. GitHub
Actions will swap in the real image on the first merge to `main`.

```bash
az containerapp create \
  --name "$CONTAINERAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$CONTAINERAPP_ENV" \
  --image mcr.microsoft.com/azuredocs/containerapps-helloworld:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2 \
  --cpu 0.5 --memory 1Gi
```

`--min-replicas 0` is the key flag: the app scales to zero when idle, so the
free monthly grant covers an idle portfolio app.

Once the GHCR image is public on your account, point the app at it. (The first
push happens automatically via `deploy.yml`.)

## 4. Federated credential for GitHub Actions → Azure (no secrets stored)

OIDC lets the workflow log in to Azure with a short-lived token instead of a
service-principal secret. Three steps: create an app registration, give it
permission on the resource group, and attach a federated credential bound to
your repo.

```bash
# Create app registration + service principal
APP_JSON=$(az ad app create --display-name forest-cover-gh-oidc)
APP_ID=$(echo "$APP_JSON" | jq -r .appId)
az ad sp create --id "$APP_ID"

# Grant Contributor on the resource group only (least privilege)
az role assignment create \
  --role Contributor \
  --assignee "$APP_ID" \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"

# Federated credential: trust pushes to main from your repo
cat <<EOF > /tmp/fic.json
{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF
az ad app federated-credential create --id "$APP_ID" --parameters @/tmp/fic.json

echo "AZURE_CLIENT_ID=$APP_ID"
echo "AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
```

If you also want to deploy from PRs (don't — but if), add a second federated
credential with `subject: repo:OWNER/REPO:pull_request`.

## 5. GitHub repo secrets

In the GitHub repo, **Settings → Secrets and variables → Actions → New
repository secret**, add:

| Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | the `APP_ID` printed above |
| `AZURE_TENANT_ID` | from the output above |
| `AZURE_SUBSCRIPTION_ID` | from the output above |
| `AZURE_RESOURCE_GROUP` | e.g. `forest-cover-rg` |
| `AZURE_CONTAINERAPP_NAME` | e.g. `forest-cover-endpoint` |

`GHCR_*` is not needed — the workflow uses the built-in `GITHUB_TOKEN` to push
to GHCR.

## 6. Make the GHCR image public (one-time)

After the first deploy run pushes the image, go to your GitHub profile →
**Packages → forest-cover-endpoint → Package settings → Change visibility →
Public**. Container Apps can pull public images without a registry credential,
which keeps the workflow simple.

## 7. Push and watch

```bash
git push origin main
gh run watch     # or open the Actions tab
```

The deploy job:
1. Trains a fresh model.
2. Builds the image.
3. Pushes to `ghcr.io/<owner>/forest-cover-endpoint:<sha>`.
4. Calls `az containerapp update --image ...`.
5. Curls `/health` against the ingress FQDN.

## 8. Hit the endpoint

```bash
URL=$(az containerapp show \
  --name "$CONTAINERAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv)

curl "https://${URL}/health"
curl -X POST "https://${URL}/predict" \
  -H 'content-type: application/json' \
  -d @../examples/spruce_fir.json
```

## Tearing it down

If you want to wipe everything and stop any chance of billing:

```bash
az group delete --name "$RESOURCE_GROUP" --yes
az ad app delete --id "$APP_ID"
```
