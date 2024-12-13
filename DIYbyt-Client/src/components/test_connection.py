#!/usr/bin/env python3
import requests
import json
import sys

def test_metadata_access(server_url):
    """Test metadata access and print detailed diagnostic information"""
    metadata_url = f"{server_url}:3001/api/metadata"
    print(f"\nTesting connection to: {metadata_url}")
    
    try:
        response = requests.get(metadata_url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {json.dumps(dict(response.headers), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nMetadata retrieved successfully:")
            print(json.dumps(data, indent=2))
            return True
        else:
            print(f"\nError: Received status code {response.status_code}")
            print(f"Response content: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"\nConnection Error: Could not connect to server")
        print(f"Error details: {str(e)}")
        return False
    except requests.exceptions.Timeout:
        print("\nTimeout Error: Server took too long to respond")
        return False
    except json.JSONDecodeError:
        print("\nJSON Decode Error: Response wasn't valid JSON")
        print(f"Raw response: {response.text}")
        return False
    except Exception as e:
        print(f"\nUnexpected Error: {str(e)}")
        return False

if __name__ == "__main__":
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.188"
    test_metadata_access(server_url)