[CmdletBinding()]
param(
    [string]$ResourceGroup = "foundry-voice-agent-rg",
    [string]$Location = "canadacentral",
    [string]$AppName = "foundry-voice-agent",
    [string]$FoundryResourceId = "",
    [Parameter(Mandatory = $true)]
    [string]$ServiceManagementReference
)

$ErrorActionPreference = "Stop"

function Invoke-AzureCli {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
}

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -eq 2) {
            $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $root ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing $envPath. Configure the existing .env file before deploying."
}

$settings = Read-DotEnv $envPath
$projectEndpoint = $settings["AZURE_AI_PROJECT_ENDPOINT"]
$agentName = $settings["AZURE_VOICE_AGENT_NAME"]
if (-not $projectEndpoint -or -not $agentName) {
    throw ".env must define AZURE_AI_PROJECT_ENDPOINT and AZURE_VOICE_AGENT_NAME."
}

Push-Location $root
try {
    $account = Invoke-AzureCli account show | ConvertFrom-Json
    $nameSuffix = $account.id.Replace("-", "").Substring(0, 8)
    $registryName = "favw$nameSuffix"
    $deploymentName = "$AppName-$Location"
    $imageTag = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
    $image = "$registryName.azurecr.io/foundry-voice-webrtc:$imageTag"
    $revisionSuffix = "r$([DateTime]::UtcNow.ToString('MMddHHmmss'))"

    $commonParameters = @(
        "environmentName=voice-demo",
        "location=$Location",
        "sessionId=$([guid]::NewGuid())",
        "deployedBy=$($account.user.name)",
        "createdAt=$([DateTime]::UtcNow.ToString('o'))",
        "resourceGroupName=$ResourceGroup",
        "containerAppName=$AppName",
        "containerEnvironmentName=$AppName-env",
        "containerRegistryName=$registryName",
        "logAnalyticsName=$AppName-logs",
        "applicationInsightsName=$AppName-insights",
        "azureAiProjectEndpoint=$projectEndpoint",
        "azureVoiceAgentName=$agentName",
        "azureApiVersion=$($settings['AZURE_API_VERSION'])",
        "foundryFeatures=$($settings['FOUNDRY_FEATURES'])"
    )

    Invoke-AzureCli deployment sub create `
        --name $deploymentName `
        --location $Location `
        --template-file infra/main.bicep `
        --parameters $commonParameters `
        --output none

    Invoke-AzureCli acr build `
        --registry $registryName `
        --image "foundry-voice-webrtc:$imageTag" `
        . `
        --output none

    $appId = "/subscriptions/$($account.id)/resourceGroups/$ResourceGroup/providers/Microsoft.App/containerApps/$AppName"
    $principalId = Invoke-AzureCli resource show `
        --ids $appId `
        --api-version 2024-03-01 `
        --query identity.principalId `
        --output tsv

    if (-not $FoundryResourceId) {
        $resourceName = ([uri]$projectEndpoint).Host.Split('.')[0]
        $FoundryResourceId = Invoke-AzureCli cognitiveservices account list `
            --query "[?name=='$resourceName'].id | [0]" `
            --output tsv
    }
    if (-not $FoundryResourceId) {
        throw "Could not find the Foundry resource. Run again with -FoundryResourceId <resource-id>."
    }

    $foundryRole = Invoke-AzureCli role assignment list `
        --assignee-object-id $principalId `
        --scope $FoundryResourceId `
        --query "[?roleDefinitionName=='Azure AI Developer'].id | [0]" `
        --output tsv
    if (-not $foundryRole) {
        Invoke-AzureCli role assignment create `
            --assignee-object-id $principalId `
            --assignee-principal-type ServicePrincipal `
            --role "Azure AI Developer" `
            --scope $FoundryResourceId `
            --output none
    }

    $fqdn = Invoke-AzureCli resource show `
        --ids $appId `
        --api-version 2024-03-01 `
        --query properties.configuration.ingress.fqdn `
        --output tsv
    $publicOrigin = "https://$fqdn"

    $entraApp = Invoke-AzureCli ad app list `
        --display-name $AppName `
        --query "[0]" `
        --output json | ConvertFrom-Json
    if (-not $entraApp) {
        $entraApp = Invoke-AzureCli ad app create `
            --display-name $AppName `
            --sign-in-audience AzureADMyOrg `
            --web-redirect-uris "$publicOrigin/.auth/login/aad/callback" `
            --enable-id-token-issuance true `
            --service-management-reference $ServiceManagementReference `
            --output json | ConvertFrom-Json
    } else {
        Invoke-AzureCli ad app update `
            --id $entraApp.appId `
            --web-redirect-uris "$publicOrigin/.auth/login/aad/callback" `
            --enable-id-token-issuance true `
            --service-management-reference $ServiceManagementReference
    }

    $servicePrincipal = Invoke-AzureCli ad sp list `
        --filter "appId eq '$($entraApp.appId)'" `
        --query "[0].id" `
        --output tsv
    if (-not $servicePrincipal) {
        Invoke-AzureCli ad sp create --id $entraApp.appId --output none
    }

    $finalParameters = $commonParameters + @(
        "revisionSuffix=$revisionSuffix",
        "containerImage=$image",
        "entraTenantId=$($account.tenantId)",
        "entraClientId=$($entraApp.appId)"
    )
    Invoke-AzureCli deployment sub create `
        --name $deploymentName `
        --location $Location `
        --template-file infra/main.bicep `
        --parameters $finalParameters `
        --output none

    $envContent = Get-Content -LiteralPath $envPath -Raw
    $envContent = [regex]::Replace($envContent, '(?m)^PUBLIC_ORIGIN=.*$', "PUBLIC_ORIGIN=$publicOrigin")
    [System.IO.File]::WriteAllText($envPath, $envContent)

    $health = Invoke-RestMethod -Uri "$publicOrigin/health"
    if ($health.status -ne "ok") {
        throw "The deployed health endpoint did not return ok."
    }
    Write-Host "Deployment completed: $publicOrigin"
    Write-Host "Microsoft Entra authentication configured for tenant $($account.tenantId)."
}
finally {
    Pop-Location
}