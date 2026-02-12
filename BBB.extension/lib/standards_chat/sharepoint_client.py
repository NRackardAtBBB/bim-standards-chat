# -*- coding: utf-8 -*-
"""
SharePoint API Client
Handles all interactions with Microsoft Graph API for SharePoint
"""

import json
import time
from standards_chat.utils import safe_print, safe_str

# Try to import IronPython .NET bridge (for pyRevit/IronPython)
# Fall back to standard Python requests if not available
try:
    import clr
    clr.AddReference('System')
    clr.AddReference('System.Net.Http')
    import System
    from System.Net.Http import HttpClient, HttpRequestMessage, HttpMethod, StringContent, ByteArrayContent
    from System.Net.Http.Headers import MediaTypeWithQualityHeaderValue, AuthenticationHeaderValue
    from System.Text import Encoding
    USE_DOTNET = True
except ImportError:
    # Running in standard Python (not IronPython)
    import requests
    USE_DOTNET = False

class SharePointClient:
    """Client for interacting with SharePoint via Microsoft Graph API"""
    
    def __init__(self, config):
        """Initialize SharePoint client"""
        self.config = config
        self.tenant_id = config.get('sharepoint', 'tenant_id')
        self.client_id = config.get('sharepoint', 'client_id')
        self.client_secret = config.get_secret('sharepoint_client_secret')
        self.site_url = config.get('sharepoint', 'site_url')
        self.site_id = config.get('sharepoint', 'site_id')
        self.api_version = config.get('sharepoint', 'api_version', default='v1.0')
        self.region = config.get('sharepoint', 'region', default='US')
        
        self.base_url = "https://graph.microsoft.com/{}".format(self.api_version)
        self.token_url = "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(self.tenant_id)
        
        self._access_token = None
        self._token_expires_at = 0
        self._site_id = None
        self._site_pages_list_id = None
        
        # Create HTTP client (either .NET or requests)
        if USE_DOTNET:
            self.client = HttpClient()
            self.client.DefaultRequestHeaders.Accept.Add(
                MediaTypeWithQualityHeaderValue("application/json")
            )
        else:
            # Using Python requests library
            self.session = requests.Session()
            self.session.headers.update({'Accept': 'application/json'})

    def _url_encode(self, s):
        """Simple URL encoding to avoid System.Uri issues"""
        if not s:
            return ""
        
        # Convert to string if needed
        s = str(s)
        
        result = []
        for char in s:
            # Alphanumeric and safe chars
            if char.isalnum() or char in '-._~':
                result.append(char)
            elif char == ' ':
                result.append('+')
            else:
                # Encode others as %XX
                result.append('%{:02X}'.format(ord(char)))
        return "".join(result)

    def _extract_keywords(self, query):
        """Extract keywords from natural language query"""
        # Simple stop words list
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", 
            "has", "he", "in", "is", "it", "its", "of", "on", "that", "the", 
            "to", "was", "were", "will", "with", "how", "do", "i", "what", 
            "where", "when", "why", "can", "you", "me", "my", "your", "we", 
            "our", "us", "please", "tell", "about"
        }
        
        # Remove punctuation
        clean_query = query.lower()
        for char in "?.,!;:\"'()":
            clean_query = clean_query.replace(char, "")
            
        words = clean_query.split()
        keywords = [w for w in words if w not in stop_words]
        
        if not keywords:
            return query # Fallback to original if everything is filtered
            
        return " ".join(keywords)

    def _log_debug(self, message):
        """Log debug message to file"""
        try:
            import os
            import datetime
            # Log to config directory in workspace
            current_dir = os.path.dirname(os.path.abspath(__file__))
            lib_dir = os.path.dirname(current_dir)
            extension_dir = os.path.dirname(lib_dir)
            log_path = os.path.join(extension_dir, 'config', 'debug.log')
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, 'a') as f:
                f.write("[{}] {}\n".format(timestamp, message))
        except Exception as e:
            # Fallback to print if file write fails
            safe_print("Logging failed: {}".format(safe_str(e)))
            safe_print(message)

    def _get_access_token(self):
        """Get or refresh OAuth2 access token"""
        self._log_debug("_get_access_token started")
        current_time = time.time()
        
        # Return cached token if valid (with 5 minute buffer)
        if self._access_token and current_time < self._token_expires_at - 300:
            self._log_debug("Using cached token")
            return self._access_token
            
        try:
            self._log_debug("Requesting new token")
            
            if USE_DOTNET:
                # .NET HttpClient approach
                content = [
                    ("client_id", self.client_id),
                    ("scope", "https://graph.microsoft.com/.default"),
                    ("client_secret", self.client_secret),
                    ("grant_type", "client_credentials")
                ]
                
                post_data = "&".join(["{}={}".format(k, self._url_encode(v)) for k, v in content])
                self._log_debug("post_data prepared")
                
                request = HttpRequestMessage(HttpMethod.Post, self.token_url)
                
                bytes_data = Encoding.UTF8.GetBytes(System.String(post_data))
                content_obj = ByteArrayContent(bytes_data)
                content_obj.Headers.ContentType = MediaTypeWithQualityHeaderValue("application/x-www-form-urlencoded")
                request.Content = content_obj
                
                self._log_debug("Sending token request")
                response = self.client.SendAsync(request).Result
                self._log_debug("Token response received: {}".format(response.StatusCode))
                
                if not response.IsSuccessStatusCode:
                    error_content = response.Content.ReadAsStringAsync().Result
                    self._log_debug("Token Error Content: {}".format(error_content))
                
                response.EnsureSuccessStatusCode()
                response_content = response.Content.ReadAsStringAsync().Result
                data = json.loads(response_content)
            else:
                # Python requests approach
                data_payload = {
                    'client_id': self.client_id,
                    'scope': 'https://graph.microsoft.com/.default',
                    'client_secret': self.client_secret,
                    'grant_type': 'client_credentials'
                }
                
                self._log_debug("Sending token request")
                response = self.session.post(
                    self.token_url,
                    data=data_payload,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                self._log_debug("Token response received: {}".format(response.status_code))
                response.raise_for_status()
                data = response.json()
            
            self._access_token = data['access_token']
            expires_in = int(data.get('expires_in', 3600))
            self._token_expires_at = current_time + expires_in
            
            # Update client headers
            if USE_DOTNET:
                self.client.DefaultRequestHeaders.Authorization = AuthenticationHeaderValue("Bearer", self._access_token)
            else:
                self.session.headers.update({'Authorization': 'Bearer {}'.format(self._access_token)})
            
            self._log_debug("Token updated successfully")
            
            return self._access_token
            
        except Exception as e:
            self._log_debug("Error getting access token: {}".format(str(e)))
            import traceback
            # traceback.print_exc() # Avoid printing to console
            raise

    def _get_site_pages_list_id(self):
        """Get the Site Pages list ID"""
        if self._site_pages_list_id:
            return self._site_pages_list_id
            
        try:
            site_id = self._get_site_id()
             # Try direct access by path
            url = "{}/sites/{}/lists/Site%20Pages".format(self.base_url, site_id)
            self._log_debug("Fetching Site Pages list from: {}".format(url))
            
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                response = self.client.SendAsync(request).Result
                if response.IsSuccessStatusCode:
                    content = response.Content.ReadAsStringAsync().Result
                    data = json.loads(content)
                    self._site_pages_list_id = data.get('id')
                    return self._site_pages_list_id
            else:
                response = self.session.get(url)
                if response.ok:
                    data = response.json()
                    self._site_pages_list_id = data.get('id')
                    return self._site_pages_list_id
            
            self._log_debug("Could not find Site Pages list by path, trying enumeration")
            # Fallback to enumeration
            url = "{}/sites/{}/lists".format(self.base_url, site_id)
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                response = self.client.SendAsync(request).Result
                if response.IsSuccessStatusCode:
                    content = response.Content.ReadAsStringAsync().Result
                    data = json.loads(content)
                    lists = data.get('value', [])
            else:
                response = self.session.get(url)
                if response.ok:
                    lists = response.json().get('value', [])
                else:
                    lists = []
                    
            for l in lists:
                if l.get('name') == 'Site Pages' or l.get('displayName') == 'Site Pages':
                    self._site_pages_list_id = l.get('id')
                    return self._site_pages_list_id
            
            self._log_debug("Site Pages list not found")
            return None
        except Exception as e:
            self._log_debug("Error getting Site Pages list ID: {}".format(str(e)))
            return None

    def _fetch_content_from_list_item(self, page_id, page_filename=None):
        """Fetch content from Site Pages list item as fallback"""
        self._log_debug("Fallback: Fetching content from list item for page {}".format(page_id))
        try:
            list_id = self._get_site_pages_list_id()
            if not list_id:
                return ""
                
            site_id = self._get_site_id()
            
            # primary attempt: use Drive API to get item by filename directly
            if page_filename:
                self._log_debug("Fetching list item via Drive API for filename: {}".format(page_filename))
                # Endpoint to get list item for a file in the default drive of the list
                url = "{}/sites/{}/lists/{}/drive/root:/{}:/listItem?$expand=fields($select=CanvasContent1,WikiField)".format(
                    self.base_url, site_id, list_id, page_filename)
                    
                self._log_debug("Drive Item Request URL: {}".format(url))
                
                item = None
                if USE_DOTNET:
                    request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                    response = self.client.SendAsync(request).Result
                    if response.IsSuccessStatusCode:
                        content = response.Content.ReadAsStringAsync().Result
                        item = json.loads(content)
                else:
                    response = self.session.get(url)
                    if response.ok:
                        item = response.json()
                
                if item:
                    fields = item.get('fields', {})
                    if 'CanvasContent1' in fields:
                        self._log_debug("Found CanvasContent1 in list item")
                        return self._extract_from_canvas_json(fields['CanvasContent1'])
                    if 'WikiField' in fields:
                        self._log_debug("Found WikiField in list item")
                        return self._strip_html(fields['WikiField'])

            # Fallback to older logic if needed (filtering)
            if page_filename:
                self._log_debug("Drive API failed. Filtering by filename: {}".format(page_filename))
                self._log_debug("Filtering by UniqueId: {}".format(page_id))
                url = "{}/sites/{}/lists/{}/items?$filter=fields/UniqueId eq '{}'&$expand=fields($select=CanvasContent1,WikiField)".format(
                    self.base_url, site_id, list_id, page_id)
            
            self._log_debug("List item request URL: {}".format(url))
            
            items = []
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                response = self.client.SendAsync(request).Result
                if response.IsSuccessStatusCode:
                    content = response.Content.ReadAsStringAsync().Result
                    data = json.loads(content)
                    items = data.get('value', [])
            else:
                response = self.session.get(url)
                if response.ok:
                    items = response.json().get('value', [])
            
            if not items and page_filename:
                 # If filename failed, try UniqueId
                 self._log_debug("Filename filter failed. Trying UniqueId.")
                 url = "{}/sites/{}/lists/{}/items?$filter=fields/UniqueId eq '{}'&$expand=fields($select=CanvasContent1,WikiField)".format(
                    self.base_url, site_id, list_id, page_id)
                 if USE_DOTNET:
                     request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                     response = self.client.SendAsync(request).Result
                     if response.IsSuccessStatusCode:
                         content = response.Content.ReadAsStringAsync().Result
                         data = json.loads(content)
                         items = data.get('value', [])
                 else:
                     response = self.session.get(url)
                     if response.ok:
                         items = response.json().get('value', [])
            
            if not items:
                self._log_debug("No items found for page fallback.")
                return ""
                
            item = items[0]
            fields = item.get('fields', {})
            
            # Check CanvasContent1
            if 'CanvasContent1' in fields:
                self._log_debug("Found CanvasContent1 in list item")
                return self._extract_from_canvas_json(fields['CanvasContent1'])
                
            # Check WikiField
            if 'WikiField' in fields:
                self._log_debug("Found WikiField in list item")
                return self._strip_html(fields['WikiField'])
                
            return ""
        except Exception as e:
            self._log_debug("Error in fallback fetch: {}".format(str(e)))
            return ""

    def _get_site_id(self):
        """Get SharePoint site ID from URL"""
        self._log_debug("_get_site_id started")
        if self._site_id:
            self._log_debug("Using cached site ID")
            return self._site_id
            
        if self.site_id:
            self._log_debug("Using configured site ID")
            self._site_id = self.site_id
            return self._site_id
            
        self._get_access_token()
        
        try:
            self._log_debug("Looking up site ID")
            # Parse hostname and path from URL
            # URL format: https://hostname/sites/sitename
            
            if USE_DOTNET:
                uri = System.Uri(System.String(self.site_url))
                hostname = uri.Host
                site_path = uri.AbsolutePath.strip('/')
            else:
                from urllib.parse import urlparse
                parsed = urlparse(self.site_url)
                hostname = parsed.hostname
                site_path = parsed.path.strip('/')
            
            url = "{}/sites/{}:/{}".format(self.base_url, hostname, site_path)
            self._log_debug("Site lookup URL: {}".format(url))
            
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                self._log_debug("Sending site ID request")
                response = self.client.SendAsync(request).Result
                self._log_debug("Site ID response: {}".format(response.StatusCode))
                response.EnsureSuccessStatusCode()
                
                content = response.Content.ReadAsStringAsync().Result
                data = json.loads(content)
            else:
                self._log_debug("Sending site ID request")
                response = self.session.get(url)
                self._log_debug("Site ID response: {}".format(response.status_code))
                response.raise_for_status()
                data = response.json()
            
            self._site_id = data['id']
            self._log_debug("Site ID found: {}".format(self._site_id))
            return self._site_id
            
        except Exception as e:
            self._log_debug("Error getting site ID: {}".format(str(e)))
            import traceback
            # traceback.print_exc()
            raise

    def get_all_pages_metadata(self):
        """
        Get metadata for all pages in the site (for indexing)
        Returns list of dicts with title, description, url
        """
        self._log_debug("get_all_pages_metadata started")
        try:
            self._get_access_token()
            site_id = self._get_site_id()
            
            # Get pages from the Site Pages library
            # We want title, description, and webUrl
            # Note: The 'pages' endpoint is a beta/v1.0 feature that simplifies this
            url = "{}/sites/{}/pages?$select=id,title,description,webUrl".format(self.base_url, site_id)
            self._log_debug("Listing all pages from {}".format(url))
            
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                response = self.client.SendAsync(request).Result
                
                if not response.IsSuccessStatusCode:
                    self._log_debug("Failed to list pages: {}".format(response.StatusCode))
                    return []
                    
                content = response.Content.ReadAsStringAsync().Result
                data = json.loads(content)
            else:
                response = self.session.get(url)
                
                if not response.ok:
                    self._log_debug("Failed to list pages: {}".format(response.status_code))
                    return []
                    
                data = response.json()
            
            pages = []
            for page in data.get('value', []):
                pages.append({
                    'id': page.get('id'),
                    'title': page.get('title'),
                    'description': page.get('description'),
                    'url': page.get('webUrl')
                })
                
            self._log_debug("Found {} pages for index".format(len(pages)))
            return pages
            
        except Exception as e:
            self._log_debug("Error getting pages metadata: {}".format(str(e)))
            return []

    def search_standards(self, query, max_results=5):
        """
        Search SharePoint site for relevant standards pages
        
        Args:
            query (str): Search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of relevant page dictionaries with content
        """
        self._log_debug("search_standards started for query: {}".format(query))
        try:
            self._get_access_token()
            site_id = self._get_site_id()
            
            # Extract keywords from natural language query
            search_terms = self._extract_keywords(query)
            self._log_debug("Original query: '{}' -> Keywords: '{}'".format(query, search_terms))
            
            # Use Microsoft Search API
            search_url = "{}/search/query".format(self.base_url)
            
            # Construct search payload
            payload = {
                "requests": [
                    {
                        "entityTypes": ["listItem"],
                        "query": {
                            "queryString": "{} path:\"{}\" filetype:aspx".format(search_terms, self.site_url)
                        },
                        "fields": ["id", "title", "webUrl", "lastModifiedDateTime", "description", "sharepointIds"],
                        "size": max_results * 2,
                        "region": self.region
                    }
                ]
            }
            
            self._log_debug("Preparing search request")
            request = HttpRequestMessage(HttpMethod.Post, search_url)
            
            # Use ByteArrayContent to avoid string encoding issues
            json_payload = json.dumps(payload)
            self._log_debug("JSON payload created")
            bytes_data = Encoding.UTF8.GetBytes(System.String(json_payload))
            content_obj = ByteArrayContent(bytes_data)
            content_obj.Headers.ContentType = MediaTypeWithQualityHeaderValue("application/json")
            request.Content = content_obj
            
            self._log_debug("Sending search request")
            response = self.client.SendAsync(request).Result
            self._log_debug("Search response: {}".format(response.StatusCode))
            
            if not response.IsSuccessStatusCode:
                error_content = response.Content.ReadAsStringAsync().Result
                self._log_debug("Search Error Content: {}".format(error_content))
                
            response.EnsureSuccessStatusCode()
            
            content = response.Content.ReadAsStringAsync().Result
            data = json.loads(content)
            
            hits = []
            if data.get('value') and len(data['value']) > 0:
                hits = data['value'][0].get('hitsContainers', [])[0].get('hits', [])
            
            self._log_debug("Found {} hits".format(len(hits)))
            
            relevant_pages = []
            for hit in hits:
                try:
                    resource = hit.get('resource', {})
                    # The ID from search is the listItem ID usually
                    list_item_id = hit.get('resource', {}).get('id')
                    
                    title = resource.get('fields', {}).get('title') or hit.get('resource', {}).get('name')
                    web_url = resource.get('webUrl')
                    
                    self._log_debug("Processing hit: {}".format(title))
                    
                    # Get SharePoint IDs
                    sp_ids = resource.get('sharepointIds', {})
                    sp_site_id = sp_ids.get('siteId') or site_id
                    sp_list_id = sp_ids.get('listId')
                    sp_item_id = sp_ids.get('listItemId')
                    
                    if sp_list_id and sp_item_id:
                        # Fetch page content
                        page_content = self._fetch_page_content(sp_site_id, sp_list_id, sp_item_id)
                    else:
                        self._log_debug("Missing IDs for hit: {}".format(title))
                        page_content = "Error: Could not resolve page IDs."
                    
                    page_data = {
                        'id': list_item_id,
                        'title': title,
                        'url': web_url,
                        'content': page_content,
                        'category': 'SharePoint Page',
                        'last_updated': resource.get('lastModifiedDateTime')
                    }
                    
                    relevant_pages.append(page_data)
                    
                    if len(relevant_pages) >= max_results:
                        break
                        
                except Exception as e:
                    self._log_debug("Error processing page {}: {}".format(hit.get('resource', {}).get('webUrl', 'unknown'), str(e)))
                    continue
            
            self._log_debug("Returning {} relevant pages".format(len(relevant_pages)))
            return relevant_pages
            
        except Exception as e:
            self._log_debug("SharePoint search failed: {}".format(str(e)))
            import traceback
            # traceback.print_exc()
            return []

    def _fetch_page_content(self, site_id, list_id, item_id):
        """Fetch content of a SharePoint page using Graph Pages API"""
        self._log_debug("_fetch_page_content started for list {} item {}".format(list_id, item_id))
        try:
            # Step 1: Get the list item with fields to find the filename
            url = "{}/sites/{}/lists/{}/items/{}/fields".format(self.base_url, site_id, list_id, item_id)
            self._log_debug("Fetching fields from {}".format(url))
            
            request = HttpRequestMessage(HttpMethod.Get, System.String(url))
            response = self.client.SendAsync(request).Result
            
            if not response.IsSuccessStatusCode:
                self._log_debug("Failed to fetch fields: {}".format(response.StatusCode))
                return "Error fetching page fields."
                
            content = response.Content.ReadAsStringAsync().Result
            fields = json.loads(content)
            
            page_filename = fields.get('LinkFilename')
            if not page_filename:
                self._log_debug("LinkFilename not found in fields")
                return "Error: Could not determine page filename."
                
            self._log_debug("Found filename: {}".format(page_filename))
            
            # Step 2: Find the page ID by matching the filename in the Pages API
            url = "{}/sites/{}/pages".format(self.base_url, site_id)
            self._log_debug("Listing pages from {}".format(url))
            
            request = HttpRequestMessage(HttpMethod.Get, System.String(url))
            response = self.client.SendAsync(request).Result
            
            if not response.IsSuccessStatusCode:
                self._log_debug("Failed to list pages: {}".format(response.StatusCode))
                return "Error listing pages."
                
            content = response.Content.ReadAsStringAsync().Result
            data = json.loads(content)
            
            page_guid = None
            for page in data.get('value', []):
                if page.get('name') == page_filename:
                    page_guid = page.get('id')
                    break
            
            if not page_guid:
                self._log_debug("Page '{}' not found in Pages API".format(page_filename))
                return "Error: Page not found."
                
            self._log_debug("Found Page GUID: {}".format(page_guid))
            
            # Step 3: Fetch the page content using the Pages API
            url = "{}/sites/{}/pages/{}/microsoft.graph.sitePage?$expand=canvasLayout".format(self.base_url, site_id, page_guid)
            self._log_debug("Fetching page content from {}".format(url))
            
            request = HttpRequestMessage(HttpMethod.Get, System.String(url))
            response = self.client.SendAsync(request).Result
            
            if not response.IsSuccessStatusCode:
                self._log_debug("Failed to fetch page content: {}".format(response.StatusCode))
                return "Error fetching page content."
                
            content = response.Content.ReadAsStringAsync().Result
            data = json.loads(content)
            
            return self._extract_text_from_canvas_layout(data)
            
        except Exception as e:
            self._log_debug("Error fetching page content: {}".format(str(e)))
            import traceback
            # traceback.print_exc()
            return "Error fetching content."

    def _extract_text_from_canvas_layout(self, page_data):
        """Extract text from the canvasLayout structure"""
        text_parts = []
        
        canvas = page_data.get("canvasLayout", {})
        if not canvas:
            self._log_debug("No canvasLayout found in page data")
            return ""
            
        self._log_debug("Canvas keys: {}".format(list(canvas.keys())))
        self._log_debug("Horizontal sections: {}".format(len(canvas.get("horizontalSections", []))))
        
        # Helper to process webparts
        def process_webparts(webparts):
            for webpart in webparts:
                wp_type = webpart.get("@odata.type")
                self._log_debug("Found webpart type: {}".format(wp_type))
                
                if wp_type == "#microsoft.graph.textWebPart":
                    inner_html = webpart.get("innerHtml", "")
                    text = self._strip_html(inner_html)
                    if text:
                        text_parts.append(text)
                # Handle other web parts that might contain text
                elif wp_type == "#microsoft.graph.standardWebPart":
                    # Sometimes text is in properties
                    props = webpart.get("data", {}).get("properties", {})
                    if props:
                        # Check common text fields
                        for key in ['text', 'content', 'description', 'title']:
                            if key in props:
                                val = props[key]
                                if isinstance(val, str):
                                    text = self._strip_html(val)
                                    if text:
                                        text_parts.append(text)

        # Check horizontal sections
        h_sections = canvas.get("horizontalSections", [])
        for i, section in enumerate(h_sections):
            columns = section.get("columns", [])
            self._log_debug("Section {}: {} columns".format(i, len(columns)))
            for j, column in enumerate(columns):
                 self._log_debug("  Column {} keys: {}".format(j, list(column.keys())))
                 webparts = column.get("webparts", [])
                 self._log_debug("  Column {}: {} webparts".format(j, len(webparts)))
                 process_webparts(webparts)
        
        # Check vertical section (if exists)
        vertical_section = canvas.get("verticalSection")
        if vertical_section:
            process_webparts(vertical_section.get("webparts", []))

        return "\n\n".join(text_parts)

    def _extract_from_canvas_json(self, canvas_json_str):
        """Extract text from CanvasContent1 JSON string"""
        if not canvas_json_str:
            return ""
            
        try:
            data = json.loads(canvas_json_str)
            text_parts = []
            
            for item in data:
                # Look for text web parts
                if item.get('webPartData'):
                    web_part_data = item.get('webPartData')
                    # Check if string (IronPython handles unicode/str differently)
                    # In IronPython, JSON strings might be System.String or python str
                    if isinstance(web_part_data, str) or isinstance(web_part_data, System.String):
                         web_part_data = json.loads(str(web_part_data))
                    
                    # Check for standard text web part
                    if web_part_data.get('title') == 'Text':
                        inner_html = web_part_data.get('properties', {}).get('text', '')
                        text = self._strip_html(inner_html)
                        if text:
                            text_parts.append(text)
                            
            return "\n\n".join(text_parts)
        except ValueError:
            # Not JSON, likely HTML storage format
            return self._strip_html(canvas_json_str)
        except Exception as e:
            self._log_debug("Error parsing canvas JSON: {}".format(str(e)))
            return self._strip_html(canvas_json_str)

    def _strip_html(self, html):
        """Remove HTML tags"""
        if not html:
            return ""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html)
    
    def _fetch_page_content_by_id(self, page_id):
        """Fetch full content of a SharePoint page by its ID"""
        self._log_debug("Fetching content by ID for: {}".format(page_id))
        try:
            site_id = self._get_site_id()
             # Use v1.0 endpoint with type casting
            url = "{}/sites/{}/pages/{}/microsoft.graph.sitePage?$expand=canvasLayout".format(self.base_url, site_id, page_id)
            self._log_debug("Request URL: {}".format(url))
            
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(url))
                response = self.client.SendAsync(request).Result
                self._log_debug("Response code: {}".format(response.StatusCode))
                
                if not response.IsSuccessStatusCode:
                    self._log_debug("Failed to fetch content for page {}: {}".format(page_id, response.StatusCode))
                    return ""
                
                content = response.Content.ReadAsStringAsync().Result
                self._log_debug("Content length: {}".format(len(content)))
                data = json.loads(content)
            else:
                response = self.session.get(url)
                if not response.ok:
                    self._log_debug("Failed to fetch content for page {}: {}".format(page_id, response.status_code))
                    return ""
                data = response.json()
                self._log_debug("Page data keys: {}".format(list(data.keys())))
                
            # Try canvas layout first
            text = self._extract_text_from_canvas_layout(data)
            if text:
                return text
                
            self._log_debug("Canvas layout empty, checking canvasContent1")
            
            # Fallback to CanvasContent1
            if 'canvasContent1' in data:
                return self._extract_from_canvas_json(data['canvasContent1'])
            
            # Additional fallback: Try fetching from list item directly
            self._log_debug("Canvas layout empty, checking list item fallback")
            page_filename = data.get('name')
            return self._fetch_content_from_list_item(page_id, page_filename)
            
        except Exception as e:
            self._log_debug("Error fetching page content by ID {}: {}".format(page_id, str(e)))
            return ""

    def get_all_pdfs_metadata(self):
        """
        Get metadata for all PDF files in the site's document libraries
        Returns list of dicts with name, url, size, downloadUrl, lastModifiedDateTime
        """
        self._log_debug("get_all_pdfs_metadata started")
        try:
            self._get_access_token()
            site_id = self._get_site_id()
            
            pdfs = []
            
            # Query the drive root for PDF files recursively
            # Start with root folder
            url = "{}/sites/{}/drive/root/children".format(self.base_url, site_id)
            self._log_debug("Querying drive for PDFs: {}".format(url))
            
            folders_to_process = [url]
            
            while folders_to_process:
                current_url = folders_to_process.pop(0)
                
                try:
                    if USE_DOTNET:
                        request = HttpRequestMessage(HttpMethod.Get, System.String(current_url))
                        response = self.client.SendAsync(request).Result
                        
                        if not response.IsSuccessStatusCode:
                            self._log_debug("Failed to list drive items: {}".format(response.StatusCode))
                            continue
                            
                        content = response.Content.ReadAsStringAsync().Result
                        data = json.loads(content)
                    else:
                        response = self.session.get(current_url)
                        
                        if not response.ok:
                            self._log_debug("Failed to list drive items: {}".format(response.status_code))
                            continue
                            
                        data = response.json()
                    
                    items = data.get('value', [])
                    
                    for item in items:
                        # Check if it's a folder
                        if 'folder' in item:
                            # Add subfolder to processing queue
                            item_id = item.get('id')
                            if item_id:
                                subfolder_url = "{}/sites/{}/drive/items/{}/children".format(
                                    self.base_url, site_id, item_id
                                )
                                folders_to_process.append(subfolder_url)
                        
                        # Check if it's a PDF file
                        elif 'file' in item:
                            name = item.get('name', '').lower()
                            if name.endswith('.pdf'):
                                # Get size and check limit
                                size = item.get('size', 0)
                                max_size = self.config.get('sharepoint', 'pdf_max_size_mb', default=50)
                                max_size_bytes = max_size * 1024 * 1024
                                
                                if size > max_size_bytes:
                                    self._log_debug("Skipping large PDF: {} ({} MB)".format(
                                        item.get('name'), size / (1024 * 1024)
                                    ))
                                    continue
                                
                                pdf_info = {
                                    'id': item.get('id'),
                                    'name': item.get('name'),
                                    'webUrl': item.get('webUrl'),
                                    'size': size,
                                    'downloadUrl': item.get('@microsoft.graph.downloadUrl'),
                                    'lastModifiedDateTime': item.get('lastModifiedDateTime')
                                }
                                pdfs.append(pdf_info)
                                
                except Exception as e:
                    self._log_debug("Error processing folder {}: {}".format(current_url, str(e)))
                    continue
            
            self._log_debug("Found {} PDFs for indexing".format(len(pdfs)))
            return pdfs
            
        except Exception as e:
            self._log_debug("Error getting PDFs metadata: {}".format(str(e)))
            return []

    def _download_pdf_file(self, pdf_metadata):
        """
        Download PDF file content from SharePoint
        
        Args:
            pdf_metadata: Dict with 'downloadUrl' key from get_all_pdfs_metadata
            
        Returns:
            bytes: PDF file content, or None on error
        """
        download_url = pdf_metadata.get('downloadUrl')
        if not download_url:
            self._log_debug("No download URL for PDF: {}".format(pdf_metadata.get('name')))
            return None
        
        try:
            self._log_debug("Downloading PDF: {}".format(pdf_metadata.get('name')))
            
            if USE_DOTNET:
                # Use .NET HttpClient - download URL doesn't need auth token
                request = HttpRequestMessage(HttpMethod.Get, System.String(download_url))
                response = self.client.SendAsync(request).Result
                
                if not response.IsSuccessStatusCode:
                    self._log_debug("Failed to download PDF: {}".format(response.StatusCode))
                    return None
                
                # Read as byte array
                byte_array = response.Content.ReadAsByteArrayAsync().Result
                # Convert .NET byte array to Python bytes
                pdf_bytes = bytes(byte_array)
                return pdf_bytes
            else:
                # Use Python requests
                response = self.session.get(download_url, timeout=30)
                
                if not response.ok:
                    self._log_debug("Failed to download PDF: {}".format(response.status_code))
                    return None
                
                return response.content
                
        except Exception as e:
            self._log_debug("Error downloading PDF {}: {}".format(pdf_metadata.get('name'), str(e)))
            return None

    def _extract_text_from_pdf(self, pdf_bytes, max_pages=100):
        """
        Extract text content from PDF bytes
        
        Args:
            pdf_bytes: PDF file content as bytes
            max_pages: Maximum number of pages to process (default 100)
            
        Returns:
            str: Extracted text content, or empty string on error
        """
        if not pdf_bytes:
            return ""
        
        try:
            import io
            from pypdf import PdfReader
            
            reader = PdfReader(io.BytesIO(pdf_bytes))
            page_limit = min(len(reader.pages), max_pages)
            
            self._log_debug("Extracting text from {} pages".format(page_limit))
            
            text_parts = []
            for i in range(page_limit):
                try:
                    page_text = reader.pages[i].extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text)
                except Exception as e:
                    # Log and continue with other pages
                    self._log_debug("Failed to extract page {}: {}".format(i, str(e)))
                    continue
            
            if not text_parts:
                self._log_debug("No text extracted from PDF")
                return ""
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            self._log_debug("PDF extraction failed: {}".format(str(e)))
            return ""

    def get_training_transcripts(self):
        """
        Get metadata for training video transcripts (.txt files) and their associated .mp4 video files.
        
        Returns list of dicts with:
            - transcript_name: Name of the .txt file
            - video_name: Name of the matching .mp4 file
            - video_url: SharePoint URL to the .mp4 video file
            - transcript_download_url: Download URL for the .txt file
            - last_modified: Last modified timestamp
        """
        self._log_debug("get_training_transcripts started")
        try:
            self._get_access_token()
            site_id = self._get_site_id()
            
            # Get the configured training videos folder path
            folder_path = self.config.get('sharepoint', 'training_videos_folder_path', 
                                         default='Training/BIM Pure Videos')
            
            self._log_debug("Scanning folder for training transcripts: {}".format(folder_path))
            
            # Build URL to query the specific folder
            url = "{}/sites/{}/drive/root:/{}:/children".format(self.base_url, site_id, folder_path)
            
            transcripts = []
            folders_to_process = [url]
            
            while folders_to_process:
                current_url = folders_to_process.pop(0)
                
                try:
                    if USE_DOTNET:
                        request = HttpRequestMessage(HttpMethod.Get, System.String(current_url))
                        response = self.client.SendAsync(request).Result
                        
                        if not response.IsSuccessStatusCode:
                            self._log_debug("Failed to list training folder items: {}".format(response.StatusCode))
                            continue
                            
                        content = response.Content.ReadAsStringAsync().Result
                        data = json.loads(content)
                    else:
                        response = self.session.get(current_url)
                        
                        if not response.ok:
                            self._log_debug("Failed to list training folder items: {}".format(response.status_code))
                            continue
                            
                        data = response.json()
                    
                    items = data.get('value', [])
                    
                    # First pass - collect all .txt and .mp4 files by folder
                    folder_files = {}
                    
                    for item in items:
                        # Check if it's a folder
                        if 'folder' in item:
                            # Add subfolder to processing queue
                            item_id = item.get('id')
                            if item_id:
                                subfolder_url = "{}/sites/{}/drive/items/{}/children".format(
                                    self.base_url, site_id, item_id
                                )
                                folders_to_process.append(subfolder_url)
                        
                        # Check if it's a file
                        elif 'file' in item:
                            name = item.get('name', '')
                            if name.endswith('.txt') or name.endswith('.mp4'):
                                folder_files[name] = item
                    
                    # Second pass - match .txt files with .mp4 files
                    for filename, item in folder_files.items():
                        if filename.endswith('.txt'):
                            # Look for matching .mp4 file
                            base_name = filename[:-4]  # Remove .txt extension
                            video_filename = base_name + '.mp4'
                            
                            if video_filename in folder_files:
                                video_item = folder_files[video_filename]
                                
                                transcript_info = {
                                    'transcript_id': item.get('id'),
                                    'transcript_name': filename,
                                    'video_id': video_item.get('id'),
                                    'video_name': video_filename,
                                    'video_url': video_item.get('webUrl'),
                                    'transcript_download_url': item.get('@microsoft.graph.downloadUrl'),
                                    'last_modified': item.get('lastModifiedDateTime'),
                                    'size': item.get('size', 0)
                                }
                                transcripts.append(transcript_info)
                            else:
                                self._log_debug("No matching video found for transcript: {}".format(filename))
                
                except Exception as e:
                    self._log_debug("Error processing training folder {}: {}".format(current_url, str(e)))
                    continue
            
            self._log_debug("Found {} training video transcripts for indexing".format(len(transcripts)))
            return transcripts
            
        except Exception as e:
            self._log_debug("Error getting training transcripts: {}".format(str(e)))
            return []

    def _download_transcript(self, transcript_metadata):
        """
        Download transcript text file content from SharePoint
        
        Args:
            transcript_metadata: Dict with transcript_download_url key
            
        Returns:
            str: Transcript text content, or empty string on error
        """
        try:
            download_url = transcript_metadata.get('transcript_download_url')
            if not download_url:
                self._log_debug("No download URL for transcript")
                return ""
            
            if USE_DOTNET:
                request = HttpRequestMessage(HttpMethod.Get, System.String(download_url))
                response = self.client.SendAsync(request).Result
                
                if not response.IsSuccessStatusCode:
                    self._log_debug("Failed to download transcript: {}".format(response.StatusCode))
                    return ""
                
                content = response.Content.ReadAsStringAsync().Result
                return content
            else:
                response = self.session.get(download_url)
                
                if not response.ok:
                    self._log_debug("Failed to download transcript: {}".format(response.status_code))
                    return ""
                
                return response.text
                
        except Exception as e:
            self._log_debug("Error downloading transcript: {}".format(str(e)))
            return ""

    def sync_to_vector_db(self, vector_db_client, progress_callback=None):
        """
        Sync all SharePoint pages to the vector database.
        
        Args:
            vector_db_client: VectorDBClient instance to index documents into
            progress_callback: Optional callback function(message, current, total) for progress updates
            
        Returns:
            Dict with sync results including document count, chunk count, and timestamp
        """
        from datetime import datetime
        
        try:
            # Update progress
            if progress_callback:
                progress_callback("Fetching SharePoint pages...", 0, 100)
            
            # Get all pages
            pages = self.get_all_pages_metadata()
            total_pages = len(pages)
            
            # Check if PDFs should be included
            include_pdfs = self.config.get('sharepoint', 'include_pdfs', default=True)
            
            # Get all PDFs if enabled
            pdfs = []
            if include_pdfs:
                if progress_callback:
                    progress_callback("Fetching PDF files...", 5, 100)
                pdfs = self.get_all_pdfs_metadata()
            
            total_pdfs = len(pdfs)
            
            # Check if training videos should be included
            include_training_videos = self.config.get('sharepoint', 'include_training_videos', default=True)
            
            # Get all training video transcripts if enabled
            training_videos = []
            if include_training_videos:
                if progress_callback:
                    progress_callback("Fetching training video transcripts...", 7, 100)
                training_videos = self.get_training_transcripts()
            
            total_videos = len(training_videos)
            
            if total_pages == 0 and total_pdfs == 0 and total_videos == 0:
                return {
                    'success': False,
                    'error': 'No pages, PDFs, or training videos found to index',
                    'documents': 0,
                    'chunks': 0,
                    'timestamp': None
                }
            
            if progress_callback:
                progress_callback("Fetching page content...", 10, 100)
            
            # Fetch full content for each page
            documents = []
            for i, page in enumerate(pages):
                try:
                    # Extract page ID from URL
                    page_url = page.get('url', '')
                    if not page_url:
                        continue
                    
                    # Get site ID and list ID (we already have them)
                    # Parse page name from URL
                    page_name = page_url.split('/')[-1]
                    
                    # Use search to get full page details
                    # Fetch full content specific page
                    page_id = page.get('id')
                    full_content = ""
                    if page_id:
                         full_content = self._fetch_page_content_by_id(page_id)
                    
                    # Combine description and full content to ensure max context
                    description = page.get('description', '')
                    parts = []
                    
                    if description:
                        parts.append(description)
                        
                    if full_content and full_content.strip() != description.strip():
                        # Only add if robust content found and not duplicate
                        parts.append(full_content)
                    
                    content = "\n\n".join(parts)
                    
                    if content:
                        documents.append({
                            'id': page_url,  # Use URL as unique ID
                            'title': page.get('title', 'Untitled'),
                            'url': page_url,
                            'content': content,
                            'category': 'SharePoint Page',
                            'last_updated': datetime.now().isoformat()
                        })
                    
                    # Update progress
                    if progress_callback:
                        progress_percent = 10 + int((i + 1) / float(total_pages) * 30)
                        progress_callback(
                            "Processed {}/{} pages".format(i + 1, total_pages),
                            progress_percent,
                            100
                        )
                
                except Exception as e:
                    self._log_debug("Error processing page {}: {}".format(page.get('title', 'Unknown'), str(e)))
                    continue
            
            # Process PDFs if enabled
            pdf_success_count = 0
            pdf_failed_count = 0
            
            if include_pdfs and pdfs:
                if progress_callback:
                    progress_callback("Processing PDF files...", 40, 100)
                
                for i, pdf in enumerate(pdfs):
                    try:
                        pdf_name = pdf.get('name', 'Unknown')
                        self._log_debug("Processing PDF {}/{}: {}".format(i + 1, total_pdfs, pdf_name))
                        
                        # Download PDF
                        pdf_bytes = self._download_pdf_file(pdf)
                        if not pdf_bytes:
                            self._log_debug("Failed to download PDF: {}".format(pdf_name))
                            pdf_failed_count += 1
                            continue
                        
                        # Extract text
                        pdf_content = self._extract_text_from_pdf(pdf_bytes)
                        
                        # Even if extraction fails, index by filename
                        if not pdf_content or not pdf_content.strip():
                            self._log_debug("No text extracted from PDF: {}".format(pdf_name))
                            # Use filename as searchable content
                            pdf_content = pdf_name
                        
                        documents.append({
                            'id': pdf.get('webUrl'),  # Use URL as unique ID
                            'title': pdf_name,
                            'url': pdf.get('webUrl'),
                            'content': pdf_content,
                            'category': 'PDF Document',
                            'last_updated': pdf.get('lastModifiedDateTime', datetime.now().isoformat())
                        })
                        
                        pdf_success_count += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_percent = 40 + int((i + 1) / float(total_pdfs) * 35)
                            progress_callback(
                                "Processed {}/{} PDFs".format(i + 1, total_pdfs),
                                progress_percent,
                                100
                            )
                    
                    except Exception as e:
                        self._log_debug("Error processing PDF {}: {}".format(pdf.get('name', 'Unknown'), str(e)))
                        pdf_failed_count += 1
                        continue
            
            # Process training video transcripts if enabled
            video_success_count = 0
            video_failed_count = 0
            
            if include_training_videos and training_videos:
                if progress_callback:
                    progress_callback("Processing training video transcripts...", 75, 100)
                
                for i, video_info in enumerate(training_videos):
                    try:
                        video_name = video_info.get('video_name', 'Unknown')
                        self._log_debug("Processing training video {}/{}: {}".format(i + 1, total_videos, video_name))
                        
                        # Download transcript text
                        transcript_content = self._download_transcript(video_info)
                        if not transcript_content or not transcript_content.strip():
                            self._log_debug("Failed to download transcript for: {}".format(video_name))
                            video_failed_count += 1
                            continue
                        
                        # Create document with video URL as reference
                        documents.append({
                            'id': video_info.get('video_url'),  # Use video URL as unique ID
                            'title': video_name.replace('.mp4', ''),  # Clean title
                            'url': video_info.get('video_url'),  # Reference points to video, not transcript
                            'content': transcript_content,
                            'category': 'Training Video',
                            'last_updated': video_info.get('last_modified', datetime.now().isoformat())
                        })
                        
                        video_success_count += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_percent = 75 + int((i + 1) / float(total_videos) * 15)
                            progress_callback(
                                "Processed {}/{} training videos".format(i + 1, total_videos),
                                progress_percent,
                                100
                            )
                    
                    except Exception as e:
                        self._log_debug("Error processing training video {}: {}".format(video_info.get('video_name', 'Unknown'), str(e)))
                        video_failed_count += 1
                        continue
            
            if not documents:
                return {
                    'success': False,
                    'error': 'No valid documents found to index',
                    'documents': 0,
                    'chunks': 0,
                    'timestamp': None
                }
            
            if progress_callback:
                progress_callback("Clearing existing index...", 90, 100)
            
            # Clear existing collection
            vector_db_client.clear_collection()
            
            if progress_callback:
                progress_callback("Generating embeddings and indexing...", 95, 100)
            
            # Index documents (this will chunk them internally)
            index_stats = vector_db_client.index_documents(documents)
            
            if progress_callback:
                progress_callback("Sync complete!", 100, 100)
            
            # Update config with sync stats
            sync_timestamp = datetime.now().isoformat()
            self.config.set_config('vector_search.last_sync_timestamp', sync_timestamp)
            self.config.set_config('vector_search.indexed_document_count', index_stats['documents'])
            self.config.set_config('vector_search.indexed_chunk_count', index_stats['chunks'])
            self.config.set_config('vector_search.indexed_pdf_count', pdf_success_count)
            self.config.set_config('vector_search.failed_pdf_count', pdf_failed_count)
            self.config.set_config('vector_search.indexed_video_count', video_success_count)
            self.config.set_config('vector_search.failed_video_count', video_failed_count)
            self.config.save()
            
            return {
                'success': True,
                'documents': index_stats['documents'],
                'chunks': index_stats['chunks'],
                'pdf_count': pdf_success_count,
                'pdf_failed': pdf_failed_count,
                'video_count': video_success_count,
                'video_failed': video_failed_count,
                'timestamp': sync_timestamp
            }
            
        except Exception as e:
            error_msg = "Sync failed: {}".format(str(e))
            self._log_debug(error_msg)
            if progress_callback:
                progress_callback(error_msg, 0, 100)
            
            return {
                'success': False,
                'error': error_msg,
                'documents': 0,
                'chunks': 0,
                'timestamp': None
            }
