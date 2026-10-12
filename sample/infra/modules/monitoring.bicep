// Monitoring, evaluator access and the GitHub Actions identity. A module of main.bicep.
param location string = resourceGroup().location
param environmentName string
param accountName string
param projectName string
@description('Object ID of the user or service principal submitting evaluations. Empty skips the role.')
param evaluatorPrincipalId string = ''
@allowed([
  'User'
  'ServicePrincipal'
])
param evaluatorPrincipalType string = 'User'
@description('GitHub owner/repository trusted for the demo environment. Empty disables the GitHub identity.')
param githubRepository string = ''
@description('True when the project identity already has Monitoring Reader on Application Insights (Foundry grants it when App Insights is connected in the portal). Azure rejects a duplicate assignment, so this skips it.')
param projectTraceReaderExists bool = false

var enableGitHub = !empty(githubRepository)
@description('Exact OIDC subject GitHub sends, e.g. repo:owner@123/name@456:environment:demo (GitHub now includes owner and repository IDs). Empty uses the classic repo:owner/name form.')
param githubOidcSubject string = ''

var githubSubject = empty(githubOidcSubject) ? 'repo:${githubRepository}:environment:demo' : githubOidcSubject

resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = if (enableGitHub) {
  name: 'id-${environmentName}-github'
  location: location
}

resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = if (enableGitHub) {
  parent: githubIdentity
  name: 'github-demo'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    audiences: [
      'api://AzureADTokenExchange'
    ]
    subject: githubSubject
  }
}

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
resource evaluatorInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(evaluatorPrincipalId)) {
  name: guid(account.id, evaluatorPrincipalId, inferenceRoleId)
  scope: account
  properties: {
    roleDefinitionId: inferenceRoleId
    principalId: evaluatorPrincipalId
    principalType: evaluatorPrincipalType
  }
}

resource githubInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableGitHub) {
  name: guid(account.id, githubIdentity!.id, inferenceRoleId)
  scope: account
  properties: {
    roleDefinitionId: inferenceRoleId
    principalId: githubIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

var contributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b24988ac-6180-42a0-ab88-20f7382dd24c'
)
resource githubDeployment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableGitHub) {
  name: guid(project.id, githubIdentity!.id, contributorRoleId)
  scope: project
  properties: {
    roleDefinitionId: contributorRoleId
    principalId: githubIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
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
resource projectTraceReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!projectTraceReaderExists) {
  name: guid(insights.id, project.id, monitoringReaderRoleId)
  scope: insights
  properties: {
    roleDefinitionId: monitoringReaderRoleId
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// The project's Application Insights connection is declared in azure.yaml (app-insights,
// host: azure.ai.connection); the Foundry provider no longer accepts it in Bicep.
#disable-next-line outputs-should-not-contain-secrets // used by the azure.yaml connection service
output applicationInsightsConnectionString string = insights.properties.ConnectionString
output applicationInsightsId string = insights.id
output applicationInsightsAppId string = insights.properties.AppId
output githubIdentityId string = enableGitHub ? githubIdentity!.id : ''
output githubClientId string = enableGitHub ? githubIdentity!.properties.clientId : ''
output githubTenantId string = enableGitHub ? githubIdentity!.properties.tenantId : ''
output githubFederatedSubject string = enableGitHub ? githubSubject : ''
