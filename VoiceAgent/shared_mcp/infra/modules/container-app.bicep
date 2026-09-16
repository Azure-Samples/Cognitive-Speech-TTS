targetScope = 'resourceGroup'

@description('Resource name.')
param name string

@description('Azure region.')
param location string = resourceGroup().location

@description('Resource tags.')
param tags object = {}

@secure()
@minLength(32)
@description('Bearer token required by both MCP routes.')
param sharedMcpToken string

@description('Container image override. A public placeholder is used during initial provision.')
param containerImage string = ''

var image = !empty(containerImage)
  ? containerImage
  : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: take('log-${name}', 63)
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: take('cae-${name}', 32)
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, {
    'azd-service-name': 'sharedmcp'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      secrets: [
        {
          name: 'shared-mcp-token'
          value: sharedMcpToken
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'sharedmcp'
          image: image
          env: [
            {
              name: 'SHARED_MCP_TOKEN'
              secretRef: 'shared-mcp-token'
            }
            {
              name: 'FINANCE_OTP_DEMO_ACCESS_CODE'
              value: '12345007'
            }
            {
              name: 'FINANCE_MCP_STATE_DIR'
              value: '/tmp/shared-mcp/finance-handoff'
            }
            {
              name: 'FINANCE_OTP_MCP_STATE_DIR'
              value: '/tmp/shared-mcp/finance-otp-officer'
            }
            {
              name: 'FINANCE_OTP_MCP_AUTH_DIR'
              value: '/tmp/shared-mcp/auth'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              periodSeconds: 5
              failureThreshold: 12
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output principalId string = app.identity.principalId

