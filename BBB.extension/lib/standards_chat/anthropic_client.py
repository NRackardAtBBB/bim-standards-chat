# -*- coding: utf-8 -*-
"""
Anthropic API Client
Handles all interactions with Claude API
"""

import json
import clr
clr.AddReference('System.Net.Http')

import System
from System.Net.Http import HttpClient, HttpRequestMessage, HttpMethod
from System.Net.Http.Headers import MediaTypeWithQualityHeaderValue
from System.Text import Encoding


def _safe_print(message):
    """Print message safely, handling Unicode errors in IronPython"""
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            print(message.encode('ascii', 'replace').decode('ascii'))
        except:
            pass


class AnthropicClient:
    """Client for interacting with Anthropic API"""
    
    def __init__(self, config):
        """Initialize Anthropic client"""
        self.config = config
        self.api_key = config.get_api_key('anthropic')
        self.model = config.get('anthropic', 'model')
        self.max_tokens = config.get('anthropic', 'max_tokens')
        self.temperature = config.get('anthropic', 'temperature')
        self.system_prompt = config.get('anthropic', 'system_prompt')
        self.base_url = "https://api.anthropic.com/v1"
        
        # Create HTTP client
        self.client = HttpClient()
        self.client.DefaultRequestHeaders.Add(
            "x-api-key",
            self.api_key
        )
        self.client.DefaultRequestHeaders.Add(
            "anthropic-version",
            "2023-06-01"
        )
        self.client.DefaultRequestHeaders.Accept.Add(
            MediaTypeWithQualityHeaderValue("application/json")
        )
    
    def _get_system_prompt(self):
        """Get system prompt, modified based on feature settings"""
        base_prompt = self.system_prompt
        
        # Check if actions are disabled
        actions_enabled = self.config.get('features', 'enable_actions', default=True)
        workflows_enabled = self.config.get('features', 'enable_workflows', default=True)
        
        if not actions_enabled and not workflows_enabled:
            # Remove the entire ACTION CAPABILITIES section
            if "ACTION CAPABILITIES:" in base_prompt:
                # Split at ACTION CAPABILITIES and take only the first part
                base_prompt = base_prompt.split("ACTION CAPABILITIES:")[0]
                base_prompt += "\n\nNote: Action capabilities are currently disabled. Provide guidance only."
        elif not workflows_enabled:
            # Remove workflows section but keep single actions
            if "WORKFLOWS - Multi-Step Actions:" in base_prompt:
                parts = base_prompt.split("WORKFLOWS - Multi-Step Actions:")
                base_prompt = parts[0]
                # Keep everything after workflows section
                if len(parts) > 1 and "Remember:" in parts[1]:
                    base_prompt += "\n\n" + parts[1].split("Remember:")[-1].strip()
                    base_prompt = "Remember:" + base_prompt.split("Remember:")[-1]
                base_prompt += "\n\nNote: Multi-step workflows are currently disabled. Only single actions are available."
        
        return base_prompt

    def generate_title(self, user_query, assistant_response):
        """
        Generate a short 3-5 word title for the conversation
        
        Args:
            user_query (str): The user's first message
            assistant_response (str): The assistant's response
            
        Returns:
            str: A short title
        """
        try:
            prompt = "Generate a very short (3-5 words) title for this conversation based on the user's request. Do not use quotes. Request: " + user_query
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            request_body = {
                "model": "claude-3-haiku-20240307", # Use fast/cheap model for titles
                "max_tokens": 20,
                "messages": messages,
                "temperature": 0.5
            }
            
            json_content = json.dumps(request_body)
            content = System.Net.Http.StringContent(
                json_content,
                Encoding.UTF8,
                "application/json"
            )
            
            # Send request
            response = self.client.PostAsync(self.base_url + "/messages", content).Result
            response_text = response.Content.ReadAsStringAsync().Result
            
            if response.IsSuccessStatusCode:
                response_json = json.loads(response_text)
                title = response_json['content'][0]['text'].strip()
                # Remove quotes if present
                if title.startswith('"') and title.endswith('"'):
                    title = title[1:-1]
                return title
            else:
                return None
                
        except Exception as e:
            _safe_print("Error generating title: {}".format(str(e)))
            return None

    def get_search_keywords(self, user_query, index_data=None):
        """
        Extract search keywords from a user query, optionally using an index
        
        Args:
            user_query (str): The user's search query
            index_data (list): Optional list of page metadata to inform keyword selection
            
        Returns:
            str: A string of keywords
        """
        try:
            if index_data:
                # Format index for prompt (limit to avoid token limits if needed, but 200 pages is fine)
                index_str = ""
                for page in index_data:
                    title = page.get('title', 'Untitled')
                    desc = page.get('description', '')
                    if desc:
                        index_str += "- {} ({})\n".format(title, desc)
                    else:
                        index_str += "- {}\n".format(title)
                
                prompt = """You are a search optimization assistant. 
Here is an index of available SharePoint pages:
{}

The user asked: '{}'

Return a list of 3-5 specific search keywords that are most likely to retrieve the relevant pages from this index. 
Focus on the terminology used in the index.
Return ONLY the keywords separated by spaces. Do not include any other text.""".format(index_str, user_query)
            else:
                prompt = "Extract 3-5 key search terms from this query. Return only the terms separated by spaces, no other text. Query: " + user_query
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            request_body = {
                "model": "claude-3-haiku-20240307", # Use fast/cheap model
                "max_tokens": 100,
                "messages": messages,
                "temperature": 0
            }
            
            json_content = json.dumps(request_body)
            content = System.Net.Http.StringContent(
                json_content,
                Encoding.UTF8,
                "application/json"
            )
            
            # Send request
            response = self.client.PostAsync(self.base_url + "/messages", content).Result
            response_text = response.Content.ReadAsStringAsync().Result
            
            if response.IsSuccessStatusCode:
                response_json = json.loads(response_text)
                text = response_json['content'][0]['text'].strip()
                
                # Extract usage
                usage = response_json.get('usage', {})
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                
                return {
                    'keywords': text,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens
                }
            else:
                _safe_print("Keyword extraction failed: " + response_text)
                return {'keywords': user_input, 'input_tokens': 0, 'output_tokens': 0}
                
        except Exception as e:
            _safe_print("Error extracting keywords: {}".format(str(e)))
            return {'keywords': user_input, 'input_tokens': 0, 'output_tokens': 0}
    
    def get_response_stream(self, user_query, notion_pages, revit_context=None, 
                           conversation_history=None, callback=None, screenshot_base64=None):
        """
        Get streaming response from Claude with RAG context
        
        Args:
            user_query (str): User's question
            notion_pages (list): Relevant Notion pages
            revit_context (dict): Optional Revit context
            conversation_history (list): Previous conversation
            callback (function): Function to call with each text chunk
            screenshot_base64 (str): Optional base64 encoded screenshot
            
        Returns:
            dict: Complete response with text and sources
        """
        # Build context from Notion pages
        context = self._build_context(notion_pages, revit_context)
        
        # Build messages array
        messages = self._build_messages(
            user_query, 
            context, 
            conversation_history,
            screenshot_base64
        )
        
        # Make streaming API call (returns dict with text and usage when available)
        stream_result = self._call_api_stream(messages, callback)
        if isinstance(stream_result, dict):
            full_text = stream_result.get('text', '')
            input_tokens = stream_result.get('input_tokens', 0)
            output_tokens = stream_result.get('output_tokens', 0)
        else:
            full_text = stream_result
            input_tokens = 0
            output_tokens = 0
        
        # Extract citations from the response
        cited_indices = self._extract_citations(full_text)
        
        # Filter sources to only include cited ones
        sources = []
        for i, page in enumerate(notion_pages, 1):  # 1-indexed to match citation numbers
            if i in cited_indices:
                sources.append({
                    'title': page['title'],
                    'url': page['url'],
                    'category': page.get('category', 'General')
                })
        
        # If no citations were found but we have pages, show top 3 as fallback
        if not sources and notion_pages:
            sources = [
                {
                    'title': page['title'],
                    'url': page['url'],
                    'category': page.get('category', 'General')
                }
                for page in notion_pages[:3]
            ]
        
        return {
            'text': full_text,
            'sources': sources,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'model': self.model
        }
    
    def get_response(self, user_query, notion_pages, revit_context=None, 
                     conversation_history=None):
        """
        Get response from Claude with RAG context
        
        Args:
            user_query (str): User's question
            notion_pages (list): Relevant Notion pages
            revit_context (dict): Optional Revit context
            conversation_history (list): Previous conversation
            
        Returns:
            dict: Response with text and sources
        """
        # Build context from Notion pages
        context = self._build_context(notion_pages, revit_context)
        
        # Build messages array
        messages = self._build_messages(
            user_query, 
            context, 
            conversation_history
        )
        
        # Make API call
        response_data = self._call_api(messages)
        
        # Extract response
        response_text = response_data['content'][0]['text']
        
        # Extract citations from the response
        cited_indices = self._extract_citations(response_text)
        
        # Filter sources to only include cited ones
        sources = []
        for i, page in enumerate(notion_pages, 1):  # 1-indexed to match citation numbers
            if i in cited_indices:
                sources.append({
                    'title': page['title'],
                    'url': page['url'],
                    'category': page.get('category', 'General')
                })
        
        # If no citations were found but we have pages, show top 3 as fallback
        if not sources and notion_pages:
            sources = [
                {
                    'title': page['title'],
                    'url': page['url'],
                    'category': page.get('category', 'General')
                }
                for page in notion_pages[:3]
            ]
        
        return {
            'text': response_text,
            'sources': sources,
            'input_tokens': response_data.get('input_tokens', 0),
            'output_tokens': response_data.get('output_tokens', 0),
            'model': self.model
        }
    
    def _extract_citations(self, text):
        """Extract citation numbers from AI response text
        
        Args:
            text (str): AI response text with citations like [1], [2]
            
        Returns:
            set: Set of citation numbers (1-indexed) that were cited
        """
        import re
        # Find all [number] patterns in the text
        citations = re.findall(r'\[(\d+)\]', text)
        # Convert to integers and return as set
        return set(int(c) for c in citations)
    
    def _build_context(self, notion_pages, revit_context):
        """Build context string from Notion pages and Revit info"""
        context_parts = []
        
        # Add Notion standards
        if notion_pages:
            context_parts.append("# Relevant BBB Standards\n")
            for i, page in enumerate(notion_pages, 1):
                context_parts.append(
                    "## Standard {}: {}\n".format(i, page['title'])
                )
                context_parts.append(
                    "Source: {}\n".format(page['url'])
                )
                if page.get('category'):
                    context_parts.append(
                        "Category: {}\n".format(page['category'])
                    )
                context_parts.append("\n{}\n\n".format(page['content']))
        
        # Add Revit context if available
        if revit_context:
            context_parts.append("\n# Current Revit Context\n")
            for key, value in revit_context.items():
                context_parts.append("- {}: {}\n".format(key, value))
        
        return ''.join(context_parts)
    
    def _build_messages(self, user_query, context, conversation_history, screenshot_base64=None):
        """Build messages array for API call"""
        messages = []
        
        # Add conversation history if present (last 3 exchanges)
        if conversation_history:
            recent_history = conversation_history[-3:]
            for exchange in recent_history:
                messages.append({
                    "role": "user",
                    "content": exchange['user']
                })
                messages.append({
                    "role": "assistant",
                    "content": exchange['assistant']
                })
        
        # Build current user message with context
        text_content = """{}

User Question: {}

Please provide a helpful, detailed answer based on BBB's standards documentation above.
IMPORTANT: When you reference information from a specific standard document, cite it using square brackets with the standard number, like [1] or [2]. These numbers correspond to the "Standard 1", "Standard 2", etc. listed above.
For example: "According to the family naming standards [1], all families should..."
Only cite sources that you actually reference in your answer.
If multiple standards are relevant, explain how they work together.
If the standards don't fully address the question, acknowledge this and provide your best guidance.""".format(
            context,
            user_query
        )
        
        # If screenshot provided, use multi-modal content format
        if screenshot_base64:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": text_content
                    }
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": text_content
            })
        
        return messages
    
    def _call_api(self, messages):
        """Make API call to Claude"""
        url = "{}/messages".format(self.base_url)
        
        # Get dynamic system prompt based on feature settings
        system_prompt = self._get_system_prompt()
        
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": messages
        }
        
        request = HttpRequestMessage(HttpMethod.Post, url)
        request.Content = System.Net.Http.StringContent(
            json.dumps(payload),
            Encoding.UTF8,
            "application/json"
        )
        
        response = self.client.SendAsync(request).Result
        
        # Check for errors
        if not response.IsSuccessStatusCode:
            error_content = response.Content.ReadAsStringAsync().Result
            raise Exception(
                "API Error ({}): {}".format(
                    response.StatusCode,
                    error_content
                )
            )
        
        content = response.Content.ReadAsStringAsync().Result
        data = json.loads(content)
        
        # Extract token usage if available
        if 'usage' in data:
            data['input_tokens'] = data['usage'].get('input_tokens', 0)
            data['output_tokens'] = data['usage'].get('output_tokens', 0)
        
        return data
    
    def _call_api_stream(self, messages, callback=None):
        """Make streaming API call to Claude"""
        url = "{}/messages".format(self.base_url)
        
        # Get dynamic system prompt based on feature settings
        system_prompt = self._get_system_prompt()
        
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": messages,
            "stream": True
        }
        
        request = HttpRequestMessage(HttpMethod.Post, url)
        request.Content = System.Net.Http.StringContent(
            json.dumps(payload),
            Encoding.UTF8,
            "application/json"
        )
        
        response = self.client.SendAsync(request, System.Net.Http.HttpCompletionOption.ResponseHeadersRead).Result
        
        # Check for errors
        if not response.IsSuccessStatusCode:
            error_content = response.Content.ReadAsStringAsync().Result
            raise Exception(
                "API Error ({}): {}".format(
                    response.StatusCode,
                    error_content
                )
            )
        
        # Read stream with UTF-8 encoding
        stream = response.Content.ReadAsStreamAsync().Result
        reader = System.IO.StreamReader(stream, Encoding.UTF8)
        
        full_text = ""
        input_tokens = 0
        output_tokens = 0

        while not reader.EndOfStream:
            line = reader.ReadLine()
            
            if not line or not line.startswith("data: "):
                continue
            
            data_str = line[6:]  # Remove "data: " prefix
            
            if data_str == "[DONE]":
                break
            
            try:
                event_data = json.loads(data_str)

                # Some streaming events include small deltas of text
                event_type = event_data.get('type')

                if event_type == 'content_block_delta':
                    delta = event_data.get('delta', {})
                    if delta.get('type') == 'text_delta':
                        text_chunk = delta.get('text', '')
                        full_text += text_chunk

                        # Call callback with chunk
                        if callback:
                            callback(text_chunk)

                # Capture usage if the API includes it in a final metadata/event payload
                # Different event shapes may place usage under top-level 'usage',
                # under 'metadata', or under a nested 'response' object. Check common locations.
                if 'usage' in event_data and isinstance(event_data['usage'], dict):
                    input_tokens = int(event_data['usage'].get('input_tokens', 0) or 0)
                    output_tokens = int(event_data['usage'].get('output_tokens', 0) or 0)
                else:
                    # Check nested locations
                    md = event_data.get('metadata') or event_data.get('response') or {}
                    if isinstance(md, dict) and 'usage' in md:
                        usage = md.get('usage', {})
                        input_tokens = int(usage.get('input_tokens', 0) or 0)
                        output_tokens = int(usage.get('output_tokens', 0) or 0)

            except Exception as e:
                _safe_print("Error parsing stream chunk: {}".format(str(e)))
                continue
        
        reader.Close()
        return {
            'text': full_text,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }
