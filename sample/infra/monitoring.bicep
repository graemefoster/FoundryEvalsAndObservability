param location string = resourceGroup().location
param environmentName string
param accountName string
param projectName string
@description('Object ID of the user or service principal submitting evaluations.')
param evaluatorPrincipalId string
@allowed([
  'User'
  'ServicePrincipal'
])
param evaluatorPrincipalType string = 'User'

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: account
  name: projectName
}

// The judge uses account-level inference; project access or OpenAI-only access is insufficient.
var inferenceRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Foundry User (formerly Azure AI User).
)
resource evaluatorInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, evaluatorPrincipalId, inferenceRoleId)
  scope: account
  properties: {
    roleDefinitionId: inferenceRoleId
    principalId: evaluatorPrincipalId
    principalType: evaluatorPrincipalType
  }
}

resource projectAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, inferenceRoleId)
  scope: project
  properties: {
    roleDefinitionId: inferenceRoleId
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${environmentName}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${environmentName}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
  }
}

var monitoringReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '43d0d8ad-25c7-4714-9337-8ba259a9fe05' // Monitoring Reader.
)
resource projectTraceReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(insights.id, project.id, monitoringReaderRoleId)
  scope: insights
  properties: {
    roleDefinitionId: monitoringReaderRoleId
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Hosting injects this connection into new sessions; the agent needs no custom tracing code.
resource connection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'app-insights'
  properties: {
    category: 'AppInsights'
    authType: 'ApiKey'
    target: insights.id
    metadata: {
      ApiType: 'Azure'
      ResourceId: insights.id
    }
    credentials: {
      key: insights.properties.ConnectionString
    }
  }
}

output applicationInsightsId string = insights.id
output applicationInsightsAppId string = insights.properties.AppId
