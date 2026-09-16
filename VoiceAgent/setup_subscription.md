# Set up a Microsoft Foundry subscription for Voice Agent samples

## Conclusion

This guide turns an otherwise empty Azure subscription into a Microsoft Foundry
Project that is ready for one of the repository's self-contained Voice Agent
examples. It is the shared setup source of truth. Do not continue to an example until
provisioning, identifiers, role assignments, preview eligibility, and region
availability are all verified.

## Completion criteria

- The selected Azure subscription is correct and enabled.
- The Voice Agent team has confirmed the subscription and region are eligible.
- `Microsoft.CognitiveServices` reports `Registered`.
- The resource group, AIServices account, and Project report `Succeeded`.
- The deployment user has both management-plane and Agent data-plane access.
- The Project managed identity has Agent data-plane access.
- `PROJECT_ENDPOINT`, `PROJECT_ID`, and `FOUNDRY_SCOPE` are populated.

## 1. Confirm preview and region eligibility

Voice Agent availability is region- and subscription-gated. Ask the Voice Agent
service owner to confirm both before creating resources. Do not copy a region
from this repository: the current repository overview names `swedencentral`
and `francecentral`, but availability can change and customer subscriptions can
have different enablement.

Do not silently substitute a normal prompt Agent or another model when
`kind: voice` or managed `gpt-realtime` is unavailable.

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
|---|---|
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

```bash
az role assignment list \
  --assignee-object-id "${USER_OBJECT_ID}" \
  --scope "${FOUNDRY_SCOPE}" \
  --include-inherited \
  --query "[].{role:roleDefinitionName,scope:scope}" \
  --output table

az role assignment list \
  --assignee-object-id "${PROJECT_PRINCIPAL_ID}" \
  --scope "${FOUNDRY_SCOPE}" \
  --include-inherited \
  --query "[].{role:roleDefinitionName,scope:scope}" \
  --output table

az cognitiveservices account project show \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${FOUNDRY_RESOURCE}" \
  --project-name "${FOUNDRY_PROJECT}" \
  --query "{state:properties.provisioningState,endpoint:properties.endpoints.\"AI Foundry API\",id:id,principalId:identity.principalId}" \
  --output json
```

Require all expected role assignments:

```bash
USER_ROLES="$(
  az role assignment list \
    --assignee-object-id "${USER_OBJECT_ID}" \
    --scope "${FOUNDRY_SCOPE}" \
    --include-inherited \
    --query "[].roleDefinitionName" \
    --output tsv
)"
PROJECT_ROLES="$(
  az role assignment list \
    --assignee-object-id "${PROJECT_PRINCIPAL_ID}" \
    --scope "${FOUNDRY_SCOPE}" \
    --include-inherited \
    --query "[].roleDefinitionName" \
    --output tsv
)"

grep -Fxq "Cognitive Services Contributor" <<<"${USER_ROLES}"
grep -Fxq "Cognitive Services User" <<<"${USER_ROLES}"
grep -Fxq "Cognitive Services User" <<<"${PROJECT_ROLES}"
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

- [Example 1: Finance with Handoff](samples/example1_finance_with_handoff/README.md)
- [Example 2: Finance with OTP and Officer Search](samples/example2_finance_with_OTP_and_Officer_Search/README.md)
- [Local template dashboard](samples/local_UI/README.md)

Those directories are self-contained after subscription setup. They own their
MCP endpoint and connection requirements, SDK installation, publication,
readback, runtime validation, and troubleshooting. Keeping those steps with the
scenario prevents a shared guide from drifting away from its `agent.json` and
`sample.py`.

## References

- [Create Microsoft Foundry Projects](https://learn.microsoft.com/azure/foundry/how-to/create-projects)
- [Microsoft Foundry RBAC](https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry)
- [Voice Agent quickstart](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-agents-quickstart)
