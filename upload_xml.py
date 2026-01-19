#!/usr/bin/env python3
"""
Simple script to upload an XML file using a presigned URL.

Usage:
    python upload_xml.py <file_path>
"""

import sys
from pathlib import Path

import requests

USER_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
API_URL = "http://localhost:8000"
USERNAME = "user@example.com"
PASSWORD = "string"


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file_path>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    filename = file_path.name
    
    # Step 1: Login to get access token
    print(f"Logging in...")
    login_url = f"{API_URL}/api/v1/auth/login"
    login_data = {
        "username": USERNAME,
        "password": PASSWORD,
    }
    
    login_response = requests.post(login_url, data=login_data)
    login_response.raise_for_status()
    login_result = login_response.json()
    access_token = login_result["access_token"]
    
    print(f"Logged in successfully")
    
    # Step 2: Get presigned URL
    print(f"Getting presigned URL...")
    url = f"{API_URL}/api/v1/users/{USER_ID}/import/apple/xml"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    data = {
        "user_id": USER_ID,
        "file_type": "application/xml",
        "filename": filename,
        "expiration_seconds": 300,
        "max_file_size": 52428800,
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    presigned_data = response.json()

    print(presigned_data)

    upload_url = presigned_data["upload_url"]
    form_fields = presigned_data["form_fields"]
    
    # Step 3: Upload file
    print(f"Uploading {filename}...")
    with open(file_path, "rb") as f:
        files = {"file": (filename, f, "application/xml")}
        upload_response = requests.post(upload_url, data=form_fields, files=files)
        upload_response.raise_for_status()
        print(upload_response)
    
    print(f"✓ Uploaded successfully! File key: {presigned_data['file_key']}")


if __name__ == "__main__":
    main()

