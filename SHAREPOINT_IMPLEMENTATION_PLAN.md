# SharePoint Integration Implementation Plan

## Overview
Add SharePoint support to the BIM Standards Chat tool to query standards from:
- **Site URL**: https://beyerblinderbelle.sharepoint.com/sites/revitstandards
- **Content Type**: Modern SharePoint pages (.aspx)
- **Search Scope**: Entire site

This will work **alongside** the existing Notion integration, allowing the organization to use either source.

---

## Phase 1: Azure AD App Registration Setup

### What IT Needs to Configure

#### 1. Create Azure AD App Registration
**Portal**: https://portal.azure.com → Azure Active Directory → App registrations → New registration

**Settings**:
- **Name**: `BBB Revit Standards Chat`
- **Supported account types**: Accounts in this organizational directory only (Single tenant)
- **Redirect URI**: Not needed (this is a desktop application)

#### 2. API Permissions Required
Add the following **Application permissions** (not Delegated):

| API | Permission | Type | Purpose |
|-----|------------|------|---------|
| Microsoft Graph | `Sites.Read.All` | Application | Read all site content |
| Microsoft Graph | `Files.Read.All` | Application | Read files in SharePoint |
| SharePoint | `Sites.Read.All` | Application | Alternative SharePoint-specific read access |

**Important**: After adding permissions, an admin must click **"Grant admin consent"** for the organization.

#### 3. Create Client Secret
- Go to **Certificates & secrets** → **New client secret**
- **Description**: `Revit Standards Chat Secret`
- **Expires**: 24 months (or per your security policy)
- **⚠️ Copy the secret value immediately** - it won't be shown again

#### 4. Information to Collect
Provide the following to the development team:

```json
{
  "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_secret": "secret_value_here",
  "site_url": "https://beyerblinderbelle.sharepoint.com/sites/revitstandards"
}
```

**Where to find these**:
- **Tenant ID**: Azure AD → Overview → Tenant ID
- **Client ID**: App registration → Overview → Application (client) ID
- **Client Secret**: Created in step 3 above
- **Site URL**: Already known (above)

---

## Phase 2: Code Implementation

### 2.1 New File: `sharepoint_client.py`
**Location**: `BBB.extension/lib/standards_chat/sharepoint_client.py`

**Features**:
- OAuth2 authentication using client credentials flow
- Microsoft Graph API integration
- Search SharePoint pages across entire site
- Extract and parse page content from modern SharePoint pages
- Cache site ID after first lookup
- Error handling and fallback mechanisms

**Key Methods**:
```python
class SharePointClient:
    def __init__(self, config)
    def _authenticate()  # Get access token via OAuth2
    def _get_site_id()  # Get site ID from URL
    def search_standards(query, max_results=5)  # Main search method
    def _search_pages(query)  # Search using Graph API
    def _fetch_page_content(page_id)  # Get full page HTML
    def _parse_page_content(html)  # Extract text from HTML
    def _extract_title(page)  # Get page title
```

### 2.2 Update: `config.json`
Add new section for SharePoint configuration:

```json
{
  "standards_source": "notion",  // or "sharepoint"
  
  "notion": {
    // ... existing config ...
  },
  
  "sharepoint": {
    "tenant_id": "",
    "client_id": "",
    "site_url": "https://beyerblinderbelle.sharepoint.com/sites/revitstandards",
    "max_search_results": 5,
    "cache_duration_minutes": 60,
    "api_version": "v1.0"
  }
}
```

### 2.3 Update: `api_keys.json`
Add SharePoint client secret:

```json
{
  "anthropic": "...",
  "notion": "...",
  "sharepoint_client_secret": ""
}
```

### 2.4 Update: `chat_window.py`
Modify to support both sources:

```python
# Initialize appropriate client based on config
standards_source = self.config.get('standards_source', 'notion')

if standards_source == 'sharepoint':
    from standards_chat.sharepoint_client import SharePointClient
    self.standards_client = SharePointClient(self.config)
else:
    from standards_chat.notion_client import NotionClient
    self.standards_client = NotionClient(self.config)

# Then use self.standards_client.search_standards() - same interface!
```

### 2.5 Update: Settings UI (`settings_window.xaml`)
Add controls to:
- Select standards source (Notion / SharePoint)
- Configure SharePoint credentials
- Test connection to verify setup

**New UI Elements**:
- Radio buttons: Notion / SharePoint
- Text fields for Tenant ID, Client ID, Site URL
- Password field for Client Secret
- "Test Connection" button
- Status indicator showing which source is active

---

## Phase 3: Technical Architecture

### Authentication Flow (SharePoint)
```
1. Application starts
2. Read client_id, client_secret, tenant_id from config
3. Request access token from Azure AD:
   POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
   Body: 
     client_id={client_id}
     client_secret={client_secret}
     scope=https://graph.microsoft.com/.default
     grant_type=client_credentials
4. Receive access token (valid ~60 minutes)
5. Use token in Authorization header for all Graph API calls
6. Cache token and refresh when expired
```

### Search Flow
```
1. User asks question
2. Extract keywords from query
3. Call Microsoft Graph Search API:
   POST https://graph.microsoft.com/v1.0/search/query
   Body: {
     "requests": [{
       "entityTypes": ["listItem"],
       "query": { "queryString": "search terms" },
       "fields": ["title", "path", "lastModifiedTime"],
       "region": "US"
     }]
   }
4. Filter results to .aspx pages from the standards site
5. For each result, fetch full page content:
   GET https://graph.microsoft.com/v1.0/sites/{site-id}/pages/{page-id}
6. Parse HTML content (web parts, text, lists, etc.)
7. Return structured results to Claude for RAG
```

### Content Extraction from Modern SharePoint Pages
Modern pages have JSON structure with web parts:
- Parse `canvasContent1` field (JSON)
- Extract text from text web parts
- Extract from list web parts
- Convert to markdown for Claude

---

## Phase 4: Dependencies

### Python Packages Needed
All available via HTTP in IronPython (no new dependencies):
- ✅ `System.Net.Http` - Already used for API calls
- ✅ `json` - Already used
- ✅ HTML parsing - Can use regex/string parsing or add `html.parser` if available

### .NET References
Already included in current implementation:
- ✅ `System.Net.Http`
- ✅ `System.Text`

---

## Phase 5: Configuration & Setup

### For IT/Admin:
1. Complete Azure AD app registration (Phase 1)
2. Provide credentials to development team
3. Test connectivity from developer machine

### For Developers:
1. Add credentials to `api_keys.json`
2. Update `standards_source` in `config.json` to "sharepoint"
3. Test authentication and search

### For End Users:
1. IT deploys updated extension files to network
2. Users open Settings in Standards Chat
3. Select "SharePoint" as source
4. Extension automatically uses SharePoint instead of Notion

---

## Phase 6: Testing Plan

### Authentication Tests
- ✅ Valid credentials → Success
- ✅ Invalid credentials → Clear error message
- ✅ Expired token → Auto-refresh
- ✅ Network issues → Graceful failure

### Search Tests
- ✅ Search returns relevant pages
- ✅ Content extraction works correctly
- ✅ HTML parsing handles all page types
- ✅ Performance acceptable (< 3 seconds)

### Integration Tests
- ✅ Chat works with SharePoint results
- ✅ Citations link to SharePoint pages
- ✅ Context provided to Claude is accurate
- ✅ Switch between Notion and SharePoint seamlessly

---

## Phase 7: Migration Strategy

### Dual-Source Support (Recommended)
Keep both Notion and SharePoint working:
- **Benefit**: Can compare both, migrate gradually
- **Config**: `standards_source` setting controls which is used
- **UI**: Settings panel lets users switch sources

### Advantages:
1. Test SharePoint before fully committing
2. Keep Notion as fallback
3. Different teams can use different sources
4. Easy rollback if issues arise

---

## Phase 8: Timeline Estimate

| Phase | Tasks | Time Estimate |
|-------|-------|--------------|
| **Phase 1** | Azure AD setup by IT | 1-2 hours |
| **Phase 2** | Code implementation | 8-12 hours |
| **Phase 3** | Testing & debugging | 4-6 hours |
| **Phase 4** | Documentation updates | 2-3 hours |
| **Phase 5** | Pilot testing | 1 week |
| **Phase 6** | Full deployment | 1-2 days |
| **Total** | | ~2-3 weeks |

---

## Phase 9: Risk Mitigation

### Potential Issues & Solutions

| Risk | Mitigation |
|------|-----------|
| **Permission denied** | Verify admin consent granted for app |
| **Site not accessible** | Test with site admin credentials first |
| **Content parsing fails** | Implement fallback to basic text extraction |
| **Token expiration** | Implement auto-refresh logic |
| **Slow performance** | Add caching layer, parallel requests |
| **HTML complexity** | Start with basic text extraction, enhance iteratively |

---

## Phase 10: Success Criteria

✅ **MVP Requirements**:
1. Authenticate to SharePoint successfully
2. Search returns relevant pages from standards site
3. Content extracted and formatted for Claude
4. Chat responses cite SharePoint pages correctly
5. Performance comparable to Notion integration

✅ **Nice-to-Have**:
1. Rich text formatting preserved
2. Images/diagrams referenced
3. Metadata filtering (modified date, author, tags)
4. Advanced search with operators
5. Usage analytics by page

---

## Next Steps

### Immediate Actions:
1. ✅ Review this plan with stakeholders
2. ⏳ Submit Azure AD app registration request to IT
3. ⏳ Receive credentials from IT
4. ⏳ Begin Phase 2 implementation
5. ⏳ Set up test environment

### Questions for IT:
1. What is your standard app secret expiration policy?
2. Can you provide a service account for testing?
3. Are there any firewall/proxy restrictions for Graph API calls?
4. Is the app registration approval process automated or manual?

---

## Appendix A: API Endpoints Reference

### Microsoft Graph API
- **Token**: `POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`
- **Search**: `POST https://graph.microsoft.com/v1.0/search/query`
- **Get Site**: `GET https://graph.microsoft.com/v1.0/sites/{hostname}:/{path}`
- **List Pages**: `GET https://graph.microsoft.com/v1.0/sites/{site-id}/pages`
- **Get Page**: `GET https://graph.microsoft.com/v1.0/sites/{site-id}/pages/{page-id}`

### Useful Documentation
- [Microsoft Graph API Reference](https://learn.microsoft.com/en-us/graph/api/overview)
- [SharePoint Pages API](https://learn.microsoft.com/en-us/graph/api/resources/sitepage)
- [Application Permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [OAuth2 Client Credentials](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-client-creds-grant-flow)

---

## Appendix B: Sample Configuration Files

### `config.json` (Complete)
```json
{
  "standards_source": "sharepoint",
  
  "anthropic": {
    "model": "claude-haiku-4-5",
    "max_tokens": 2048,
    "temperature": 0.7,
    "system_prompt": "..."
  },
  
  "notion": {
    "database_id": "...",
    "api_version": "2022-06-28",
    "max_search_results": 5,
    "cache_duration_minutes": 60
  },
  
  "sharepoint": {
    "tenant_id": "",
    "client_id": "",
    "site_url": "https://beyerblinderbelle.sharepoint.com/sites/revitstandards",
    "max_search_results": 5,
    "cache_duration_minutes": 60,
    "api_version": "v1.0"
  },
  
  "features": {
    "include_context": false,
    "include_screenshot": false,
    "enable_actions": false,
    "enable_workflows": false
  },
  
  "logging": {
    "enabled": true,
    "analytics_enabled": true
  },
  
  "ui": {
    "window_width": 500,
    "window_height": 700,
    "theme": "light"
  }
}
```

### `api_keys.json` (Complete)
```json
{
  "anthropic": "sk-ant-...",
  "notion": "secret_...",
  "sharepoint_client_secret": "..."
}
```

---

## Document Version
- **Created**: November 20, 2025
- **Version**: 1.0
- **Status**: Draft for Review
