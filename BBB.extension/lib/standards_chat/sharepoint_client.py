# -*- coding: utf-8 -*-
"""
SharePoint API Client
Handles all interactions with Microsoft Graph API for SharePoint
"""

import json
import time
import clr
clr.AddReference('System')
clr.AddReference('System.Net.Http')

import System
from System.Net.Http import HttpClient, HttpRequestMessage, HttpMethod, StringContent, ByteArrayContent
from System.Net.Http.Headers import MediaTypeWithQualityHeaderValue, AuthenticationHeaderValue
from System.Text import Encoding

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
        
        # Create HTTP client
        self.client = HttpClient()
        self.client.DefaultRequestHeaders.Accept.Add(
            MediaTypeWithQualityHeaderValue("application/json")
        )

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
            print("Logging failed: {}".format(str(e)))
            print(message)

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
            # Prepare request for client credentials flow
            content = [
                ("client_id", self.client_id),
                ("scope", "https://graph.microsoft.com/.default"),
                ("client_secret", self.client_secret),
                ("grant_type", "client_credentials")
            ]
            
            # Convert to form url encoded content manually
            # Use custom url encode to avoid .NET casting issues
            post_data = "&".join(["{}={}".format(k, self._url_encode(v)) for k, v in content])
            self._log_debug("post_data prepared")
            
            request = HttpRequestMessage(HttpMethod.Post, self.token_url)
            
            # Use ByteArrayContent to avoid string encoding issues
            self._log_debug("Creating ByteArrayContent for token request")
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
            
            self._access_token = data['access_token']
            expires_in = int(data.get('expires_in', 3600))
            self._token_expires_at = current_time + expires_in
            
            # Update client headers
            self.client.DefaultRequestHeaders.Authorization = AuthenticationHeaderValue("Bearer", self._access_token)
            self._log_debug("Token updated successfully")
            
            return self._access_token
            
        except Exception as e:
            self._log_debug("Error getting access token: {}".format(str(e)))
            import traceback
            # traceback.print_exc() # Avoid printing to console
            raise

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
            uri = System.Uri(System.String(self.site_url))
            hostname = uri.Host
            site_path = uri.AbsolutePath.strip('/')
            
            url = "{}/sites/{}:/{}".format(self.base_url, hostname, site_path)
            self._log_debug("Site lookup URL: {}".format(url))
            
            request = HttpRequestMessage(HttpMethod.Get, System.String(url))
            self._log_debug("Sending site ID request")
            response = self.client.SendAsync(request).Result
            self._log_debug("Site ID response: {}".format(response.StatusCode))
            response.EnsureSuccessStatusCode()
            
            content = response.Content.ReadAsStringAsync().Result
            data = json.loads(content)
            
            self._site_id = data['id']
            self._log_debug("Site ID found: {}".format(self._site_id))
            return self._site_id
            
        except Exception as e:
            self._log_debug("Error getting site ID: {}".format(str(e)))
            import traceback
            # traceback.print_exc()
            raise

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
            return ""
        
        # Check horizontal sections
        h_sections = canvas.get("horizontalSections", [])
        
        for section in h_sections:
            columns = section.get("columns", [])
            for column in columns:
                webparts = column.get("webparts", [])
                for webpart in webparts:
                    wp_type = webpart.get("@odata.type")
                    
                    if wp_type == "#microsoft.graph.textWebPart":
                        inner_html = webpart.get("innerHtml", "")
                        text = self._strip_html(inner_html)
                        if text:
                            text_parts.append(text)
        
        # Check vertical section (if exists)
        vertical_section = canvas.get("verticalSection")
        if vertical_section:
            for webpart in vertical_section.get("webparts", []):
                 if webpart.get("@odata.type") == "#microsoft.graph.textWebPart":
                    inner_html = webpart.get("innerHtml", "")
                    text = self._strip_html(inner_html)
                    if text:
                        text_parts.append(text)

        return "\n\n".join(text_parts)

    def _extract_from_canvas_json(self, canvas_json_str):
        """Extract text from CanvasContent1 JSON string"""
        try:
            if not canvas_json_str:
                return ""
                
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
        except Exception as e:
            self._log_debug("Error parsing canvas JSON: {}".format(str(e)))
            return ""

    def _strip_html(self, html):
        """Remove HTML tags"""
        if not html:
            return ""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html)
