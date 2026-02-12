"""
Debug script to check what's in the training videos folder on SharePoint
"""
import sys
import os

# Add extension lib path
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, 'BBB.extension', 'lib')
sys.path.insert(0, lib_path)

from standards_chat.config_manager import ConfigManager
from standards_chat.sharepoint_client import SharePointClient

def main():
    print("\n" + "="*60)
    print("Training Folder Debug - Checking SharePoint Structure")
    print("="*60 + "\n")
    
    # Load config
    config = ConfigManager()
    
    # Get folder path from config
    folder_path = config.get('sharepoint', 'training_videos_folder_path', 
                            default='Documents/Training/BIM Pure Videos')
    
    print("Configuration:")
    print(f"  Folder path: {folder_path}")
    print(f"  Include training videos: {config.get('sharepoint', 'include_training_videos', default=True)}")
    print()
    
    # Initialize SharePoint client
    print("Initializing SharePoint client...")
    sp_client = SharePointClient(config)
    
    # First, let's see what's in the Documents folder
    print("\nListing folders in SharePoint root...")
    print("-" * 60)
    
    try:
        sp_client._get_access_token()
        site_id = sp_client._get_site_id()
        
        # List root items - use requests since we're in CPython
        import json
        import requests
        
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {sp_client._access_token}',
            'Accept': 'application/json'
        })
        
        url = f"{sp_client.base_url}/sites/{site_id}/drive/root/children"
        response = session.get(url)
        
        if response.ok:
            data = response.json()
            items = data.get('value', [])
            
            print("\nFolders in root:")
            for item in items:
                if 'folder' in item:
                    print(f"  - {item.get('name')}")
        
        # Try Documents folder
        url = f"{sp_client.base_url}/sites/{site_id}/drive/root:/Documents:/children"
        response = session.get(url)
        
        if response.ok:
            data = response.json()
            items = data.get('value', [])
            
            print("\nFolders in Documents:")
            for item in items:
                if 'folder' in item:
                    print(f"  - {item.get('name')}")
        else:
            print(f"\n  Documents folder not found or not accessible (Status: {response.status_code})")
            
    except Exception as e:
        print(f"  Error listing folders: {str(e)}")
    
    # Try to get training transcripts
    print(f"\nSearching for training video transcripts in: {folder_path}")
    print("-" * 60)
    
    transcripts = sp_client.get_training_transcripts()
    
    print(f"\nResults:")
    print(f"  Found {len(transcripts)} training video transcript(s)")
    
    if transcripts:
        print("\nTraining Videos Found:")
        for i, transcript in enumerate(transcripts, 1):
            print(f"\n  [{i}] Video: {transcript.get('video_name')}")
            print(f"      Transcript: {transcript.get('transcript_name')}")
            print(f"      Video URL: {transcript.get('video_url')}")
            print(f"      Size: {transcript.get('size', 0)} bytes")
    else:
        print("\n  No training video transcripts found!")
        print("\n  Possible reasons:")
        print("  1. The folder path might be incorrect")
        print("  2. There are no .txt files in that location")
        print("  3. .txt files exist but don't have matching .mp4 files")
        print("\n  Please verify:")
        print(f"  - Does 'Documents/Training/BIM Pure Videos' exist on SharePoint?")
        print(f"  - Are there .txt AND .mp4 files with matching names in subfolders?")
    
    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()
