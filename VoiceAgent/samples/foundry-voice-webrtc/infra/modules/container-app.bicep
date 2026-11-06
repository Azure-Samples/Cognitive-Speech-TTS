param containerAppName string
param environmentName string
param location string
param tags object
param workspaceCustomerId string
@secure()
param workspaceSharedKey string
param acrLoginServer string
param containerImage string
param appInsightsConnectionString string
@secure()
param azureAiProjectEndpoint string
@secure()
param azureVoiceAgentName string
@secure()
param azureApiVersion string
@secure()
param foundryFeatures string
@secure()
param iceServersJson string
param appPort int = 8080
param revisionSuffix string = 'icefix'
param entraTenantId string = ''
param entraClientId string = ''

@secure()
param entraClientSecret string = ''

var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var isPlaceholder = containerImage == placeholderImage
var effectivePort = isPlaceholder ? 80 : appPort
var entraEnabled = !empty(entraTenantId) && !empty(entraClientId)
var entraSecretEnabled = !empty(entraClientSecret)

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspaceCustomerId
        sharedKey: workspaceSharedKey
      }
    }
    zoneRedundant: false
  }
}

var publicOrigin = 'https://${containerAppName}.${environment.properties.defaultDomain}'

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: effectivePort
        transport: 'auto'
        allowInsecure: false
      }
      registries: isPlaceholder ? [] : [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: concat([
          {
            name: 'ice-servers-json'
            value: iceServersJson
          }
        ], entraSecretEnabled ? [
          {
            name: 'microsoft-provider-authentication-secret'
            value: entraClientSecret
          }
        ] : [])
    }
    template: {
      revisionSuffix: revisionSuffix
      containers: [
        {
          name: 'app'
          image: containerImage
          env: [
            {
              name: 'AZURE_AI_PROJECT_ENDPOINT'
              value: azureAiProjectEndpoint
            }
            {
              name: 'AZURE_VOICE_AGENT_NAME'
              value: azureVoiceAgentName
            }
            {
              name: 'AZURE_API_VERSION'
              value: azureApiVersion
            }
            {
              name: 'FOUNDRY_FEATURES'
              value: foundryFeatures
            }
            {
              name: 'ICE_SERVERS_JSON'
              secretRef: 'ice-servers-json'
            }
            {
              name: 'PORT'
              value: string(effectivePort)
            }
            {
              name: 'PUBLIC_ORIGIN'
              value: publicOrigin
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: isPlaceholder ? '/' : '/health'
                port: effectivePort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2024-03-01' = {
  parent: containerApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: union({
        unauthenticatedClientAction: entraEnabled ? 'RedirectToLoginPage' : 'Return401'
        excludedPaths: [
          '/health'
        ]
      }, entraEnabled ? {
        redirectToProvider: 'azureactivedirectory'
      } : {})
    httpSettings: {
      requireHttps: true
    }
    identityProviders: entraEnabled ? {
      azureActiveDirectory: {
        enabled: true
        registration: union({
            clientId: entraClientId
            openIdIssuer: '${az.environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
          }, entraSecretEnabled ? {
            clientSecretSettingName: 'microsoft-provider-authentication-secret'
          } : {})
        validation: {
          allowedAudiences: [
            entraClientId
          ]
        }
      }
    } : {}
    login: {
      tokenStore: {
        enabled: entraSecretEnabled
      }
    }
  }
}

output id string = containerApp.id
output principalId string = containerApp.identity.principalId
output fqdn string = containerApp.properties.configuration.ingress.fqdn
output publicOrigin string = publicOrigin
