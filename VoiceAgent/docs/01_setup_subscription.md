# 01 - Set up a Microsoft Foundry subscription

## Conclusion

This guide selects an existing Microsoft Foundry Project or creates one in an
empty Azure subscription. It is the shared source of truth for subscription,
Project endpoint, permissions, model mode, and region eligibility. Do not
continue to an example until those values are verified.

After completing the criteria below, continue with
[02: MCP settings, deployment, and development](./02_mcp_settings.md).

## Completion criteria

- The selected Azure subscription is correct and enabled.
- The Voice Agent team has confirmed the subscription and region are eligible.
- `Microsoft.CognitiveServices` reports `Registered`.
- The resource group, AIServices account, and Project report `Succeeded`.
- The deployment user has both management-plane and Agent data-plane access.
- The Project managed identity has Agent data-plane access.
- `PROJECT_ENDPOINT`, `PROJECT_ID`, and `FOUNDRY_SCOPE` are populated.
- The Finance definitions' `model_type` and exact `model` identifier match a
  mode available to the Project.

## 1. Confirm preview and region eligibility

Voice Agent availability is region- and subscription-gated. Ask the Voice Agent
service owner to confirm both before creating resources. Do not copy a region
from this repository: the current repository overview names `swedencentral`
and `francecentral`, but availability can change and customer subscriptions can
have different enablement.

Do not silently substitute a normal prompt Agent or change to self-deployed
mode when `kind: voice` or the requested managed realtime model is unavailable.

The two Finance definitions default to this versioned service-managed Voice
Agent model:

```json
"model_type": "managed",
"model": "gpt-realtime-2.1"
```

This does not reference a customer-created account deployment. Managed model
identifiers vary by Project. Start with `gpt-realtime-2.1`. If publication
reports it unsupported, explicitly set `VOICE_AGENT_MODEL=gpt-realtime-1.5`
and retry. If neither is enabled, use another exact managed identifier
confirmed for that Project, such as `gpt-realtime-2.1-mini`; do not use the
unversioned `gpt-realtime` alias as a compatibility fallback.

Set the same `VOICE_AGENT_MODEL` value in both Finance sample `.env` files and
the Local UI `.env`. If every confirmed versioned identifier fails, use a
Project in an eligible region or ask the Voice Agent service owner to confirm
the subscription-region-model combination. Do not change the sample to
self-deployed mode to work around a managed-model failure.

## 2. Install tools and sign in

Install:

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- Git
- Python 3.10 or later
- Bash 4 or later
- `curl` and `jq`

On Windows, use WSL for the Bash commands.

Sign in and select the customer subscription:

```bash
az login

SUBSCRIPTION="<subscription-name-or-id>"
az account set --subscription "${SUBSCRIPTION}"

az account show \
  --query "{name:name,id:id,tenantId:tenantId,state:state}" \
  --output table
```

Stop if the displayed subscription is not the one the customer intends to use.

Subscription aliases used in conversation or internal documentation may not
be accepted by Azure CLI. Resolve the exact name or ID with a structured query:

```bash
az account list --all \
  --query "[?contains(name, 'Online') || contains(name, 'Meeting')].{name:name,id:id,state:state,isDefault:isDefault}" \
  --output table
```

Use words relevant to the customer's subscription instead of `Online` and
`Meeting`. Then set `SUBSCRIPTION` to the returned exact name or ID.

## Existing Project fast path

Do this before creating resources when the customer already has a Foundry
Project. Project names are nested ARM resource names, so a plain
`az resource list --name <project>` can return no result even when the Project
exists.

When the Project name is unknown, enumerate all Projects in the active
subscription first:

```bash
az resource list \
  --resource-type Microsoft.CognitiveServices/accounts/projects \
  --query "[].{name:name,resourceGroup:resourceGroup,location:location,id:id}" \
  --output table
```

Select only a Project whose account, resource group, workload owner, purpose,
and confirmed Voice Agent region match the customer setup. Resource discovery
does not prove that an unrelated Project is approved for this workload. Ask
the customer for the intended Project ARM ID when those criteria do not select
one unambiguously.

```bash
FOUNDRY_PROJECT="<existing-project-name>"

PROJECT_ID="$(
  az resource list \
    --resource-type Microsoft.CognitiveServices/accounts/projects \
    --query "[?ends_with(name, '/${FOUNDRY_PROJECT}')].id | [0]" \
    --output tsv
)"

: "${PROJECT_ID:?Project was not found in the active subscription}"

PROJECT_ENDPOINT="$(
  az rest \
    --method get \
    --url "https://management.azure.com${PROJECT_ID}?api-version=2025-06-01" \
    --query 'properties.endpoints."AI Foundry API"' \
    --output tsv
)"

FOUNDRY_SCOPE="${PROJECT_ID%/projects/*}"
FOUNDRY_RESOURCE="${FOUNDRY_SCOPE##*/}"
RESOURCE_GROUP="${PROJECT_ID#*/resourceGroups/}"
RESOURCE_GROUP="${RESOURCE_GROUP%%/*}"
LOCATION="$(
  az rest \
    --method get \
    --url "https://management.azure.com${PROJECT_ID}?api-version=2025-06-01" \
    --query location \
    --output tsv
)"

printf 'PROJECT_ENDPOINT=%s\nPROJECT_ID=%s\nFOUNDRY_SCOPE=%s\nRESOURCE_GROUP=%s\nFOUNDRY_RESOURCE=%s\nLOCATION=%s\n' \
  "${PROJECT_ENDPOINT}" \
  "${PROJECT_ID}" \
  "${FOUNDRY_SCOPE}" \
  "${RESOURCE_GROUP}" \
  "${FOUNDRY_RESOURCE}" \
  "${LOCATION}"
```

If multiple Projects with the same name are visible, query all matches and
select by account, resource group, and subscription instead of taking `[0]`:

```bash
az resource list \
  --resource-type Microsoft.CognitiveServices/accounts/projects \
  --query "[?ends_with(name, '/${FOUNDRY_PROJECT}')].{name:name,id:id,resourceGroup:resourceGroup,location:location}" \
  --output table
```

Verify the returned endpoint has this exact shape:

```text
https://<account>.services.ai.azure.com/api/projects/<project>
```

Then continue with identity and role verification in sections 7 through 11.
Do not run the resource creation sections for an existing Project.

## 3. Choose names

The Foundry account name must be globally unique because it becomes part of the
service endpoint.

```bash
LOCATION="<confirmed-supported-region>"
RESOURCE_GROUP="rg-voice-agent-samples"
FOUNDRY_RESOURCE="<globally-unique-foundry-resource-name>"
FOUNDRY_PROJECT="voice-agent-samples"
```

Keep the variables in the same shell for the rest of this guide.

## 4. Register the provider

```bash
az provider register \
  --namespace Microsoft.CognitiveServices \
  --wait

az provider show \
  --namespace Microsoft.CognitiveServices \
  --query registrationState \
  --output tsv
```

The final output must be:

```text
Registered
```

## 5. Create the resource group and Foundry account

```bash
az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}"
```

Create an AIServices account with Project management and a system-assigned
identity:

```bash
az cognitiveservices account create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FOUNDRY_RESOURCE}" \
  --kind AIServices \
  --sku S0 \
  --location "${LOCATION}" \
  --custom-domain "${FOUNDRY_RESOURCE}" \
  --assign-identity \
  --allow-project-management true \
  --yes
```

Verify:

```bash
az cognitiveservices account show \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FOUNDRY_RESOURCE}" \
  --query "{location:location,state:properties.provisioningState,projectManagement:properties.allowProjectManagement,id:id}" \
  --output table
```

Expected values are the chosen location, `Succeeded`, and `true`.

Make those expectations hard gates:

```bash
ACCOUNT_STATE="$(
  az cognitiveservices account show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --query properties.provisioningState \
    --output tsv
)"
PROJECT_MANAGEMENT="$(
  az cognitiveservices account show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --query properties.allowProjectManagement \
    --output tsv
)"

test "${ACCOUNT_STATE}" = "Succeeded"
test "${PROJECT_MANAGEMENT,,}" = "true"
```

## 6. Create the Foundry Project

```bash
az cognitiveservices account project create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FOUNDRY_RESOURCE}" \
  --project-name "${FOUNDRY_PROJECT}" \
  --location "${LOCATION}"
```

Capture the identifiers used by SDK and management-plane commands:

```bash
PROJECT_ENDPOINT="$(
  az cognitiveservices account project show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --project-name "${FOUNDRY_PROJECT}" \
    --query "properties.endpoints.\"AI Foundry API\"" \
    --output tsv
)"

PROJECT_ID="$(
  az cognitiveservices account project show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --project-name "${FOUNDRY_PROJECT}" \
    --query id \
    --output tsv
)"

FOUNDRY_SCOPE="$(
  az cognitiveservices account show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --query id \
    --output tsv
)"

printf 'PROJECT_ENDPOINT=%s\nPROJECT_ID=%s\nFOUNDRY_SCOPE=%s\n' \
  "${PROJECT_ENDPOINT}" \
  "${PROJECT_ID}" \
  "${FOUNDRY_SCOPE}"
```

Expected formats:

```text
PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
PROJECT_ID=/subscriptions/<id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>
FOUNDRY_SCOPE=/subscriptions/<id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>
```

Require all three values:

```bash
: "${PROJECT_ENDPOINT:?Project endpoint was not returned}"
: "${PROJECT_ID:?Project ARM ID was not returned}"
: "${FOUNDRY_SCOPE:?Foundry account ARM ID was not returned}"

PROJECT_STATE="$(
  az cognitiveservices account project show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --project-name "${FOUNDRY_PROJECT}" \
    --query properties.provisioningState \
    --output tsv
)"
test "${PROJECT_STATE}" = "Succeeded"
```

Account deployment lists describe customer-created deployments. They do not
prove whether the service-managed Voice Agent model is enabled. Use the
publication and session gates in [03: Start and run the samples](./03_run_samples.md)
after preview eligibility and region support are confirmed.

## 7. Resolve identity object IDs without Microsoft Graph

Decode the deployment identity's object ID from an ARM access token. This
avoids requiring a separate Microsoft Graph sign-in:

```bash
ARM_ACCESS_TOKEN="$(
  az account get-access-token \
    --resource https://management.azure.com/ \
    --query accessToken \
    --output tsv
)"

USER_OBJECT_ID="$(
  ARM_ACCESS_TOKEN="${ARM_ACCESS_TOKEN}" python3 - <<'PY'
import base64
import json
import os

payload = os.environ["ARM_ACCESS_TOKEN"].split(".")[1]
payload += "=" * (-len(payload) % 4)
print(json.loads(base64.urlsafe_b64decode(payload))["oid"])
PY
)"

unset ARM_ACCESS_TOKEN

PROJECT_PRINCIPAL_ID="$(
  az cognitiveservices account project show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${FOUNDRY_RESOURCE}" \
    --project-name "${FOUNDRY_PROJECT}" \
    --query identity.principalId \
    --output tsv
)"

: "${USER_OBJECT_ID:?Could not determine deployment user object ID}"
: "${PROJECT_PRINCIPAL_ID:?The Project has no managed identity principal ID}"
```

## 8. Assign the required roles

The examples need two permission planes:

| Role | Why |
| --- | --- |
| `Cognitive Services Contributor` | Create and manage the Foundry account, Project, and Project connections |
| `Cognitive Services User` | Call the AIServices Agent data-plane APIs, including Agent create/read/invoke |

Assign both to the deployment user at the Foundry account scope:

```bash
az role assignment create \
  --assignee-object-id "${USER_OBJECT_ID}" \
  --assignee-principal-type User \
  --role "Cognitive Services Contributor" \
  --scope "${FOUNDRY_SCOPE}"

az role assignment create \
  --assignee-object-id "${USER_OBJECT_ID}" \
  --assignee-principal-type User \
  --role "Cognitive Services User" \
  --scope "${FOUNDRY_SCOPE}"
```

Give the Project managed identity Agent data-plane access:

```bash
az role assignment create \
  --assignee-object-id "${PROJECT_PRINCIPAL_ID}" \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" \
  --scope "${FOUNDRY_SCOPE}"
```

The person running these commands must have
`Microsoft.Authorization/roleAssignments/write`. If an organization uses ABAC
conditions or privileged identity management, an administrator may need to
perform or activate the assignment.

Organizations can replace these roles with custom least-privilege roles, but
the replacement must include the corresponding management actions and
`Microsoft.CognitiveServices/accounts/AIServices/agents/*` data actions.

## 9. Verify roles and provisioning

Use ARM REST for role verification. Unlike `az role assignment list`, these
queries do not ask Microsoft Graph to resolve principal display information.
The principal filter includes assignments inherited from parent scopes.

```bash
AUTHORIZATION_API_VERSION="2022-04-01"

role_definition_id() {
  local role_name="$1"
  az rest \
    --method get \
    --url "https://management.azure.com${FOUNDRY_SCOPE}/providers/Microsoft.Authorization/roleDefinitions?api-version=${AUTHORIZATION_API_VERSION}" \
    --url-parameters "\$filter=roleName eq '${role_name}'" \
    --query "value[0].id" \
    --output tsv
}

principal_role_definition_ids() {
  local principal_id="$1"
  az rest \
    --method get \
    --url "https://management.azure.com${FOUNDRY_SCOPE}/providers/Microsoft.Authorization/roleAssignments?api-version=${AUTHORIZATION_API_VERSION}" \
    --url-parameters "\$filter=principalId eq '${principal_id}'" \
    --query "value[].properties.roleDefinitionId" \
    --output tsv
}

CONTRIBUTOR_ROLE_ID="$(role_definition_id "Cognitive Services Contributor")"
USER_ROLE_ID="$(role_definition_id "Cognitive Services User")"
USER_ROLE_IDS="$(principal_role_definition_ids "${USER_OBJECT_ID}")"
PROJECT_ROLE_IDS="$(principal_role_definition_ids "${PROJECT_PRINCIPAL_ID}")"

: "${CONTRIBUTOR_ROLE_ID:?Could not resolve Cognitive Services Contributor}"
: "${USER_ROLE_ID:?Could not resolve Cognitive Services User}"

grep -Fxiq "${CONTRIBUTOR_ROLE_ID}" <<<"${USER_ROLE_IDS}"
grep -Fxiq "${USER_ROLE_ID}" <<<"${USER_ROLE_IDS}"
grep -Fxiq "${USER_ROLE_ID}" <<<"${PROJECT_ROLE_IDS}"

az cognitiveservices account project show \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FOUNDRY_RESOURCE}" \
  --project-name "${FOUNDRY_PROJECT}" \
  --query "{state:properties.provisioningState,endpoint:properties.endpoints.\"AI Foundry API\",id:id,principalId:identity.principalId}" \
  --output json
```

Role assignments can take several minutes to propagate. Wait and retry the
data-plane operation before changing the role set. If the Azure CLI is signed
in as the wrong identity or tenant, run `az login` again and reselect
`${SUBSCRIPTION}`. Then restore the shell variables or rerun the capture
commands above.

## 10. Preserve the non-secret outputs

Store these values in a password manager, deployment system, or protected
customer setup record:

```text
SUBSCRIPTION
LOCATION
RESOURCE_GROUP
FOUNDRY_RESOURCE
FOUNDRY_PROJECT
PROJECT_ENDPOINT
PROJECT_ID
FOUNDRY_SCOPE
```

They are identifiers, not bearer credentials, but they still disclose customer
topology and should not be added to a reusable public sample.

## 11. Point a sample at this Project

Do not copy an endpoint from a demo, TIP, or another customer's subscription.
Use the `${PROJECT_ENDPOINT}` produced above as
`AZURE_AI_PROJECT_ENDPOINT` in the selected example's ignored `.env`.

Continue in exactly one scenario README:

- [02: MCP settings, deployment, and development](./02_mcp_settings.md)
- [03: Start and run the samples](./03_run_samples.md)
- [Example 1: Finance with Handoff](../samples/example1_finance_with_handoff/README.md)
- [Example 2: Finance with OTP and Officer Search](../samples/example2_finance_with_OTP_and_Officer_Search/README.md)
- [Local UI](../samples/local_UI/README.md)
- [Finance examples architecture and documentation index](./README.md)

Those directories are self-contained after subscription setup. They own their
MCP endpoint and connection requirements, SDK installation, publication,
readback, runtime validation, and troubleshooting. Keeping those steps with the
scenario prevents a shared guide from drifting away from its `agent.json` and
`sample.py`.

## References

- [Create Microsoft Foundry Projects](https://learn.microsoft.com/azure/foundry/how-to/create-projects)
- [Microsoft Foundry RBAC](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry)
- [Voice Agent quickstart](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-agents-quickstart)
