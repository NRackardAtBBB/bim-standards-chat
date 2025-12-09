import json
import os
import urllib.request
import urllib.parse
import urllib.error
import sys
import re

# Configuration paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'BBB.extension', 'config', 'config.json')
KEYS_PATH = os.path.join(BASE_DIR, 'BBB.extension', 'config', 'api_keys.json')

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def get_token(tenant_id, client_id, client_secret):
    url = "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(tenant_id)
    data = urllib.parse.urlencode({
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))['access_token']
    except urllib.error.HTTPError as e:
        print(f"Error getting token: {e}")
        print(e.read().decode('utf-8'))
        sys.exit(1)

def get_site_id(token, site_url):
    # Return known ID to avoid lookup issues
    known_id = "beyerblinderbelle.sharepoint.com,fc5e6d27-c959-415e-b0a8-eca5d2452de5,80b30066-9432-4e94-aa57-518588ca5d5e"
    print(f"Using known Site ID: {known_id}")
    return known_id

    # Parse hostname and path from URL
    # URL format: https://hostname/sites/sitename
    parsed = urllib.parse.urlparse(site_url)
    hostname = parsed.netloc
    site_path = parsed.path.strip('/')
    
    url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}"
    print(f"Looking up site ID: {url}")
    
    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data['id']
    except urllib.error.HTTPError as e:
        print(f"Error getting site ID: {e}")
        return None

def strip_html(html):
    """Remove HTML tags"""
    if not html:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', html)

def extract_from_canvas_json(canvas_json_str):
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
                # Check if string (sometimes it's double encoded)
                if isinstance(web_part_data, str):
                        web_part_data = json.loads(web_part_data)
                
                # Check for standard text web part
                if web_part_data.get('title') == 'Text':
                    inner_html = web_part_data.get('properties', {}).get('text', '')
                    text = strip_html(inner_html)
                    if text:
                        text_parts.append(text)
                        
        return "\n\n".join(text_parts)
    except Exception as e:
        print(f"Error parsing canvas JSON: {str(e)}")
        return ""

def extract_content_from_item(data):
    text_content = ""
    if 'fields' in data:
        if 'CanvasContent1' in data['fields']:
            text_content = extract_from_canvas_json(data['fields']['CanvasContent1'])
        elif 'WikiField' in data['fields']:
            text_content = strip_html(data['fields']['WikiField'])
    return text_content

def fetch_page_content_via_graph_pages_api(token, site_id, list_id, item_id):
    """
    Fetch content using the Microsoft Graph Pages API.
    """
    # Step 1: Get the list item with fields to find the filename
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}?$expand=fields"
    print(f"  -> Fetching List Item fields: {url}")
    
    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {token}')
    
    page_filename = None
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            fields = data.get('fields', {})
            
            if 'LinkFilename' in fields:
                page_filename = fields['LinkFilename']
                print(f"  -> Found Filename: {page_filename}")
            else:
                print("  -> LinkFilename not found in fields.")
                print(f"DEBUG: Available Fields: {list(fields.keys())}")
                return "Error: Could not determine page filename."
                
    except urllib.error.HTTPError as e:
        print(f"  -> Failed to fetch item fields: {e}")
        return "Error: Failed to resolve Page Filename."

    # Step 2: Find the page ID by matching the filename in the Pages API
    # We list all pages and match because $filter might be tricky with filenames/titles
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages"
    print(f"  -> Looking up Page ID for '{page_filename}' in Pages API...")
    
    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {token}')
    
    page_guid = None
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            for page in data.get('value', []):
                if page.get('name') == page_filename:
                    page_guid = page.get('id')
                    print(f"  -> Found Page GUID: {page_guid}")
                    break
            
            if not page_guid:
                print(f"  -> Page '{page_filename}' not found in Pages API list.")
                return "Error: Page not found."
                
    except urllib.error.HTTPError as e:
        print(f"  -> Failed to list pages: {e}")
        return "Error: Failed to lookup Page ID."

    # Step 3: Fetch the page content using the Pages API
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages/{page_guid}/microsoft.graph.sitePage?$expand=canvasLayout"
    print(f"  -> Fetching Page Content: {url}")
    
    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # DEBUG: Check for canvasLayout
            if 'canvasLayout' in data:
                print("DEBUG: canvasLayout found")
            else:
                print("DEBUG: canvasLayout NOT found in response")
                print(f"DEBUG: Available keys: {list(data.keys())}")
                
            return extract_text_from_canvas_layout(data)
    except urllib.error.HTTPError as e:
        print(f"  -> Failed to fetch page content: {e}")
        try:
            print(f"DEBUG: Error Body: {e.read().decode('utf-8')}")
        except:
            pass
        return "Error fetching page content."

def extract_text_from_canvas_layout(page_data):
    """Extract text from the canvasLayout structure"""
    text_parts = []
    
    canvas = page_data.get("canvasLayout", {})
    if not canvas:
        print("DEBUG: canvasLayout is empty")
        return ""
    
    # Check horizontal sections
    h_sections = canvas.get("horizontalSections", [])
    print(f"DEBUG: Found {len(h_sections)} horizontal sections")
    
    for i, section in enumerate(h_sections):
        columns = section.get("columns", [])
        for j, column in enumerate(columns):
            webparts = column.get("webparts", [])
            for k, webpart in enumerate(webparts):
                wp_type = webpart.get("@odata.type")
                # print(f"DEBUG: Webpart [{i}][{j}][{k}] type: {wp_type}")
                
                if wp_type == "#microsoft.graph.textWebPart":
                    inner_html = webpart.get("innerHtml", "")
                    text = strip_html(inner_html)
                    if text:
                        text_parts.append(text)
                        print(f"DEBUG: Extracted text ({len(text)} chars)")
    
    # Check vertical section (if exists)
    vertical_section = canvas.get("verticalSection")
    if vertical_section:
        print("DEBUG: Vertical section found")
        for webpart in vertical_section.get("webparts", []):
             if webpart.get("@odata.type") == "#microsoft.graph.textWebPart":
                inner_html = webpart.get("innerHtml", "")
                text = strip_html(inner_html)
                if text:
                    text_parts.append(text)

    return "\n\n".join(text_parts)

def fetch_page_content_with_ids(token, site_id, list_id, item_id):
    """Fetch content using precise IDs from sharepointIds"""
    # Try the Pages API approach first (Modern Pages)
    return fetch_page_content_via_graph_pages_api(token, site_id, list_id, item_id)

def test_list_pages(token, site_id):
    print(f"\n--- Testing List Pages ---")
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages"
    print(f"GET {url}")
    
    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"Found {len(data.get('value', []))} pages.")
            for i, page in enumerate(data.get('value', [])):
                title = page.get('title')
                pid = page.get('id')
                name = page.get('name')
                web_url = page.get('webUrl')
                print(f"Page: '{title}' | Name: '{name}' | ID: {pid}")
                
                if title == "Line Weight Guidelines":
                    print(f"*** FOUND TARGET PAGE *** ID: {pid}")

    except urllib.error.HTTPError as e:
        print(f"List Pages failed: {e}")
        try:
            print(f"Error Body: {e.read().decode('utf-8')}")
        except:
            pass

def search(token, query, site_url, region="US"):
    # First get site ID for content fetching
    config_site_id = get_site_id(token, site_url)
    
    # Test listing pages to verify ID format and permissions
    # test_list_pages(token, config_site_id)
    
    url = "https://graph.microsoft.com/v1.0/search/query"
    
    kql_query = '{} path:"{}" filetype:aspx'.format(query, site_url)
    print(f"\nTesting Query: {kql_query}")
    
    payload = {
        "requests": [
            {
                "entityTypes": ["listItem"],
                "query": {
                    "queryString": kql_query
                },
                # Request sharepointIds to get the exact list and item IDs
                "fields": ["id", "title", "webUrl", "lastModifiedDateTime", "description", "sharepointIds"],
                "size": 10,
                "region": region
            }
        ]
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')
    
    found_links = []

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            hits = result['value'][0]['hitsContainers'][0].get('hits', [])
            print(f"Found {len(hits)} hits.")
            for hit in hits:
                res = hit['resource']
                title = res.get('fields', {}).get('title', 'No Title')
                web_url = res.get('webUrl')
                
                found_links.append({'title': title, 'url': web_url})

                # Get SharePoint IDs
                sp_ids = res.get('sharepointIds', {})
                
                sp_site_id = sp_ids.get('siteId')
                if not sp_site_id:
                    sp_site_id = config_site_id
                    
                sp_list_id = sp_ids.get('listId')
                sp_item_id = sp_ids.get('listItemId')
                
                print(f"\n--- HIT: {title} ---")
                print(f"URL: {web_url}")
                print(f"SP IDs: Site={sp_site_id}, List={sp_list_id}, Item={sp_item_id}")
                
                if sp_site_id and sp_list_id and sp_item_id:
                    content = fetch_page_content_with_ids(token, sp_site_id, sp_list_id, sp_item_id)
                    preview = content[:200].replace('\n', ' ') + "..." if content else "No content extracted."
                    print(f"CONTENT PREVIEW: {preview}")
                else:
                    print("Could not get necessary IDs to fetch content.")
            
            print("\n" + "="*50)
            print("RELEVANT PAGES FOUND:")
            print("="*50)
            for link in found_links:
                print(f"• {link['title']}")
                print(f"  {link['url']}")
            print("="*50 + "\n")
                    
            return result
    except urllib.error.HTTPError as e:
        print(f"Search failed: {e}")
        print(e.read().decode('utf-8'))

def main():
    print("Loading config...")
    if not os.path.exists(CONFIG_PATH) or not os.path.exists(KEYS_PATH):
        print("Config files not found!")
        return

    config = load_json(CONFIG_PATH)
    keys = load_json(KEYS_PATH)
    
    tenant_id = config['sharepoint']['tenant_id']
    client_id = config['sharepoint']['client_id']
    site_url = config['sharepoint']['site_url']
    region = config['sharepoint'].get('region', 'US')
    client_secret = keys['sharepoint_client_secret']
    
    print("Authenticating...")
    token = get_token(tenant_id, client_id, client_secret)
    print("Authentication successful.")
    
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        print("Using default query: 'line weights'")
        query = "line weights"
        
    search(token, query, site_url, region)

if __name__ == "__main__":
    main()
