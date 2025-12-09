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
        
        # Make streaming API call
        full_text = self._call_api_stream(messages, callback)
        
        # Format sources
        sources = [
            {
                'title': page['title'],
                'url': page['url'],
                'category': page.get('category', 'General')
            }
            for page in notion_pages
        ]
        
        return {
            'text': full_text,
            'sources': sources
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
        
        # Format sources
        sources = [
            {
                'title': page['title'],
                'url': page['url'],
                'category': page.get('category', 'General')
            }
            for page in notion_pages
        ]
        
        return {
            'text': response_text,
            'sources': sources
        }
    
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
When referencing specific standards, mention them by name.
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
        
        while not reader.EndOfStream:
            line = reader.ReadLine()
            
            if not line or not line.startswith("data: "):
                continue
            
            data_str = line[6:]  # Remove "data: " prefix
            
            if data_str == "[DONE]":
                break
            
            try:
                event_data = json.loads(data_str)
                event_type = event_data.get('type')
                
                if event_type == 'content_block_delta':
                    delta = event_data.get('delta', {})
                    if delta.get('type') == 'text_delta':
                        text_chunk = delta.get('text', '')
                        full_text += text_chunk
                        
                        # Call callback with chunk
                        if callback:
                            callback(text_chunk)
            except Exception as e:
                print("Error parsing stream chunk: {}".format(str(e)))
                continue
        
        reader.Close()
        return full_text
