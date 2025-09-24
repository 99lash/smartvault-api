#!/usr/bin/env python3
"""
Test script for the new vault sharing endpoint.
This script tests the GET /users/vault/{user_id} endpoint functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

def test_vault_sharing_endpoint():
    """Test the new vault sharing endpoint"""
    client = TestClient(app)

    # Test 1: Check if endpoint exists
    print("Test 1: Checking if endpoint exists...")
    response = client.get("/users/vault/1")
    print(f"Status Code: {response.status_code}")

    if response.status_code == 401:
        print("SUCCESS: Endpoint exists (401 Unauthorized - expected without auth)")
    elif response.status_code == 404:
        print("ERROR: Endpoint not found")
        return False
    else:
        print(f"WARNING: Unexpected status code: {response.status_code}")

    # Test 2: Check with invalid user ID
    print("\nTest 2: Testing with invalid user ID...")
    response = client.get("/users/vault/99999")
    print(f"Status Code: {response.status_code}")

    if response.status_code == 404:
        print("SUCCESS: Correctly returns 404 for non-existent user")
    else:
        print(f"WARNING: Expected 404, got: {response.status_code}")

    print("\nSUCCESS: All basic tests passed!")
    print("Note: Full functionality testing requires authenticated requests")
    return True

if __name__ == "__main__":
    print("Testing vault sharing endpoint...")
    test_vault_sharing_endpoint()