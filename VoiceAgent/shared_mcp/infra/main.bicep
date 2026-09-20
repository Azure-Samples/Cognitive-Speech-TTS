targetScope = 'subscription'

@minLength(1)
@maxLength(32)
@description('Name of the azd environment.')
param environmentName string

@description('Azure region for the deployment.')
param location string

@secure()
@minLength(32)
@description('Bearer token required by both MCP routes.')
param sharedMcpToken string

@description('Container image set by azd after the initial provision.')
param containerImage string = ''

var normalizedEnvironmentName = toLower(replace(environmentName, '-', ''))
var resourceSuffix = take(uniqueString(subscription().id, environmentName, location), 6)
var resourceGroupName = 'rg-${environmentName}'
var containerRegistryName = take('cr${normalizedEnvironmentName}${resourceSuffix}', 50)
var containerAppName = take('ca-${environmentName}-${resourceSuffix}', 32)
var tags = {
  'azd-env-name': environmentName
  workload: 'voice-agent-shared-mcp'
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module registry './modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: resourceGroup
  params: {
    name: containerRegistryName
    location: location
    tags: tags
  }
}

module app './modules/container-app.bicep' = {
  name: 'container-app'
  scope: resourceGroup
  params: {
    name: containerAppName
    location: location
    tags: tags
    sharedMcpToken: sharedMcpToken
    containerImage: containerImage
  }
}

module acrPull './modules/acr-pull-role.bicep' = {
  name: 'container-app-acr-pull'
  scope: resourceGroup
  params: {
    name: 'ra-${containerAppName}-acrpull'
    location: location
    tags: tags
    acrName: registry.outputs.name
    principalId: app.outputs.principalId
  }
}

output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = registry.outputs.name
output AZURE_CONTAINER_APP_NAME string = app.outputs.name
output SHARED_MCP_BASE_URL string = 'https://${app.outputs.fqdn}'
output SHARED_MCP_ELEVATOR_SERVICE_URL string = 'https://${app.outputs.fqdn}/mcp/elevator-service'
output SHARED_MCP_FINANCE_HANDOFF_URL string = 'https://${app.outputs.fqdn}/mcp/finance-handoff'
output SHARED_MCP_FINANCE_OTP_OFFICER_URL string = 'https://${app.outputs.fqdn}/mcp/finance-otp-officer'
