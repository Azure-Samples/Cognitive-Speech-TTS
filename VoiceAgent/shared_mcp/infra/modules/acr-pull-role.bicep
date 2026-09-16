targetScope = 'resourceGroup'

@description('Resource name used to seed the deterministic role-assignment GUID.')
param name string

@description('Azure region. Included for a consistent module contract.')
#disable-next-line no-unused-params
param location string = resourceGroup().location

@description('Resource tags. Included for a consistent module contract.')
#disable-next-line no-unused-params
param tags object = {}

@description('Azure Container Registry name.')
param acrName string

@description('Container App system-assigned managed identity principal ID.')
param principalId string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, principalId, name)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
