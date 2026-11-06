targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string

param sessionId string
param deployedBy string
param createdAt string
param resourceGroupName string
param containerAppName string
param containerEnvironmentName string
param containerRegistryName string
param logAnalyticsName string
param applicationInsightsName string
param revisionSuffix string = 'icefix'
param entraTenantId string = ''
param entraClientId string = ''

@secure()
param entraClientSecret string = ''
@secure()
param azureAiProjectEndpoint string

@secure()
param azureVoiceAgentName string

@secure()
param azureApiVersion string

@secure()
param foundryFeatures string

param iceServersJson string = '[{"urls":"stun:stun.l.google.com:19302"}]'

param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var tags = {
  'app-onboard-skill': 'true'
  'app-onboard-session-id': sessionId
  'created-at': createdAt
  environment: environmentName
  'deployed-by': deployedBy
  OwnerAlias: split(deployedBy, '@')[0]
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module logAnalytics './modules/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: resourceGroup
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
  }
}

module applicationInsights './modules/app-insights.bicep' = {
  name: 'application-insights'
  scope: resourceGroup
  params: {
    name: applicationInsightsName
    location: location
    tags: tags
    workspaceId: logAnalytics.outputs.id
  }
}

module containerRegistry './modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: resourceGroup
  params: {
    name: containerRegistryName
    location: location
    tags: tags
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'container-app'
  scope: resourceGroup
  params: {
    containerAppName: containerAppName
    environmentName: containerEnvironmentName
    location: location
    tags: tags
    workspaceCustomerId: logAnalytics.outputs.customerId
    workspaceSharedKey: logAnalytics.outputs.sharedKey
    acrLoginServer: containerRegistry.outputs.loginServer
    containerImage: containerImage
    appInsightsConnectionString: applicationInsights.outputs.connectionString
    azureAiProjectEndpoint: azureAiProjectEndpoint
    azureVoiceAgentName: azureVoiceAgentName
    azureApiVersion: azureApiVersion
    foundryFeatures: foundryFeatures
    iceServersJson: iceServersJson
    revisionSuffix: revisionSuffix
    entraTenantId: entraTenantId
    entraClientId: entraClientId
    entraClientSecret: entraClientSecret
  }
}

module roleAssignments './modules/role-assignments.bicep' = {
  name: 'role-assignments'
  scope: resourceGroup
  params: {
    acrName: containerRegistryName
    appPrincipalId: containerApp.outputs.principalId
  }
}

output resourceGroupName string = resourceGroup.name
output containerAppId string = containerApp.outputs.id
output containerAppPrincipalId string = containerApp.outputs.principalId
output containerAppFqdn string = containerApp.outputs.fqdn
output publicOrigin string = containerApp.outputs.publicOrigin
output containerRegistryId string = containerRegistry.outputs.id
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
output logAnalyticsId string = logAnalytics.outputs.id
output applicationInsightsId string = applicationInsights.outputs.id
output acrPullRoleAssignmentId string = roleAssignments.outputs.acrPullRoleAssignmentId
