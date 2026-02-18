# -*- coding: utf-8 -*-
"""
Notion API Client
Handles all interactions with Notion API
"""

import json
import clr
from standards_chat.utils import safe_str, safe_print
clr.AddReference('System.Net.Http')

import System
from System.Net.Http import HttpClient, HttpRequestMessage, HttpMethod
from System.Net.Http.Headers import MediaTypeWithQualityHeaderValue
from System.Text import Encoding


class NotionClient:
    """Client for interacting with Notion API"""
    
    def __init__(self, config):
        """Initialize Notion client"""
        self.config = config
        self.api_key = config.get_api_key('notion')
        self.database_id = config.get('notion', 'database_id')
        self.api_version = config.get('notion', 'api_version')
        self.base_url = "https://api.notion.com/v1"
        
        # Create HTTP client
        self.client = HttpClient()
        self.client.DefaultRequestHeaders.Add(
            "Authorization", 
            "Bearer {}".format(self.api_key)
        )
        self.client.DefaultRequestHeaders.Add(
            "Notion-Version", 
            self.api_version
        )
        self.client.DefaultRequestHeaders.Accept.Add(
            MediaTypeWithQualityHeaderValue("application/json")
        )
    
    def search_standards(self, query, max_results=5):
        """
        Search Notion database for relevant standards
        
        Args:
            query (str): Search query
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of relevant page dictionaries with content
        """
        # Query the specific database with text filter
        search_results = self._query_database(query)
        
        # Process results
        relevant_pages = []
        for result in search_results[:max_results * 2]:  # Get more results to filter
            try:
                # Fetch full page content
                page_content = self._fetch_page_content(result['id'])
                
                # Extract metadata
                page_data = {
                    'id': result['id'],
                    'title': self._extract_title(result),
                    'url': result['url'],
                    'content': page_content,
                    'category': self._extract_property(result, 'Category'),
                    'last_updated': self._extract_property(result, 'Last Updated')
                }
                
                relevant_pages.append(page_data)
                
                # Stop if we have enough
                if len(relevant_pages) >= max_results:
                    break
                    
            except Exception as e:
                # Log error but continue with other pages
                safe_print(u"Error processing page {}: {}".format(
                    result.get('id', 'unknown'), 
                    safe_str(e)
                ))
                continue
        
        return relevant_pages
    
    def _query_database(self, query):
        """Query the specific standards database"""
        # Try database query first
        try:
            url = "{}/databases/{}/query".format(self.base_url, self.database_id)
            
            payload = {
                "page_size": 20,
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": "descending"
                    }
                ]
            }
            
            request = HttpRequestMessage(HttpMethod.Post, url)
            request.Content = System.Net.Http.StringContent(
                json.dumps(payload),
                Encoding.UTF8,
                "application/json"
            )
            
            response = self.client.SendAsync(request).Result
            
            # If 404, the integration may not have access to this database
            if response.StatusCode.value__ == 404:
                print("Database not accessible, falling back to search API")
                return self._search_and_filter(query)
            
            response.EnsureSuccessStatusCode()
            
            content = response.Content.ReadAsStringAsync().Result
            data = json.loads(content)
            all_results = data.get('results', [])
            
        except Exception as e:
            safe_print(u"Database query failed: {}, falling back to search".format(safe_str(e)))
            return self._search_and_filter(query)
        
        # Filter results by query match in title
        query_lower = query.lower()
        scored_results = []
        
        for page in all_results:
            title = self._extract_title(page).lower()
            score = 0
            
            # Check if query words are in title
            query_words = query_lower.split()
            for word in query_words:
                if word in title:
                    score += 10  # High score for title match
            
            if score > 0 or len(query_words) == 0:
                scored_results.append((score, page))
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        return [page for score, page in scored_results]
    
    def _search_and_filter(self, query):
        """Fallback: use search API and filter by database"""
        url = "{}/search".format(self.base_url)
        
        payload = {
            "query": query,
            "filter": {
                "value": "page",
                "property": "object"
            },
            "page_size": 20
        }
        
        request = HttpRequestMessage(HttpMethod.Post, url)
        request.Content = System.Net.Http.StringContent(
            json.dumps(payload),
            Encoding.UTF8,
            "application/json"
        )
        
        response = self.client.SendAsync(request).Result
        response.EnsureSuccessStatusCode()
        
        content = response.Content.ReadAsStringAsync().Result
        data = json.loads(content)
        
        # Filter to only pages from our database
        results = []
        for page in data.get('results', []):
            parent = page.get('parent', {})
            if parent.get('type') == 'database_id':
                db_id = parent.get('database_id', '').replace('-', '')
                config_db_id = self.database_id.replace('-', '')
                if db_id == config_db_id:
                    results.append(page)
        
        return results
    
    def _fetch_page_content(self, page_id):
        """Fetch full content of a Notion page"""
        url = "{}/blocks/{}/children".format(self.base_url, page_id)
        
        request = HttpRequestMessage(HttpMethod.Get, url)
        response = self.client.SendAsync(request).Result
        response.EnsureSuccessStatusCode()
        
        content = response.Content.ReadAsStringAsync().Result
        data = json.loads(content)
        
        blocks = data.get('results', [])
        
        # Convert blocks to text
        text_content = self._blocks_to_text(blocks)
        
        return text_content
    
    def _blocks_to_text(self, blocks):
        """Convert Notion blocks to plain text"""
        text_parts = []
        
        for block in blocks:
            block_type = block.get('type')
            
            if block_type == 'paragraph':
                text = self._extract_rich_text(block['paragraph'])
                if text:
                    text_parts.append(text)
            
            elif block_type == 'heading_1':
                text = self._extract_rich_text(block['heading_1'])
                if text:
                    text_parts.append("\n## {}".format(text))
            
            elif block_type == 'heading_2':
                text = self._extract_rich_text(block['heading_2'])
                if text:
                    text_parts.append("\n### {}".format(text))
            
            elif block_type == 'heading_3':
                text = self._extract_rich_text(block['heading_3'])
                if text:
                    text_parts.append("\n#### {}".format(text))
            
            elif block_type == 'bulleted_list_item':
                text = self._extract_rich_text(block['bulleted_list_item'])
                if text:
                    text_parts.append("- {}".format(text))
            
            elif block_type == 'numbered_list_item':
                text = self._extract_rich_text(block['numbered_list_item'])
                if text:
                    text_parts.append("- {}".format(text))
            
            elif block_type == 'code':
                text = self._extract_rich_text(block['code'])
                if text:
                    text_parts.append("\n```\n{}\n```".format(text))
            
            elif block_type == 'quote':
                text = self._extract_rich_text(block['quote'])
                if text:
                    text_parts.append("> {}".format(text))
        
        return "\n".join(text_parts)
    
    def _extract_rich_text(self, block_content):
        """Extract plain text from rich text array, filtering out problematic Unicode"""
        rich_text = block_content.get('rich_text', [])
        text_parts = []
        for rt in rich_text:
            plain_text = rt.get('plain_text', '')
            # Filter out characters that can't be encoded in IronPython
            # Keep printable ASCII and common whitespace/punctuation
            filtered_text = ''.join(
                char for char in plain_text 
                if ord(char) < 127 or (127 <= ord(char) < 0xFFFF and char in '\n\r\t ')
            )
            text_parts.append(filtered_text)
        return ''.join(text_parts)
    
    def _is_standards_page(self, page):
        """Check if page belongs to standards database"""
        # Check if page has parent database matching standards DB
        parent = page.get('parent', {})
        if parent.get('type') == 'database_id':
            return parent.get('database_id') == self.database_id
        return False
    
    def _extract_title(self, page):
        """Extract title from page object"""
        properties = page.get('properties', {})
        
        # Try common title property names
        for key in ['Name', 'Title', 'Standard Name', 'title', 'name']:
            if key in properties:
                prop = properties[key]
                prop_type = prop.get('type', '')
                
                if prop_type == 'title':
                    title_array = prop.get('title', [])
                    if title_array and len(title_array) > 0:
                        title = title_array[0].get('plain_text', '')
                        return self._clean_unicode(title)
                elif prop_type == 'rich_text':
                    rich_text_array = prop.get('rich_text', [])
                    if rich_text_array and len(rich_text_array) > 0:
                        title = rich_text_array[0].get('plain_text', '')
                        return self._clean_unicode(title)
        
        # Fallback to ID if no title found
        return page.get('id', 'Untitled')
    
    def _clean_unicode(self, text):
        """Remove problematic Unicode characters for IronPython"""
        if not text:
            return text
        # Keep only ASCII printable chars and common whitespace
        return ''.join(
            char for char in text 
            if ord(char) < 127 or (127 <= ord(char) < 0xFFFF and char in '\n\r\t ')
        )
    
    def _extract_property(self, page, prop_name):
        """Extract property value from page"""
        try:
            properties = page.get('properties', {})
            prop = properties.get(prop_name, {})
            prop_type = prop.get('type')
            
            if prop_type == 'select':
                return prop['select'].get('name')
            elif prop_type == 'date':
                return prop['date'].get('start')
            elif prop_type == 'multi_select':
                return [item['name'] for item in prop['multi_select']]
            
        except:
            pass
        return None
