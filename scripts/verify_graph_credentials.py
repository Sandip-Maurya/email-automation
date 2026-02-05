"""
Simple script to verify Microsoft Graph API credentials and read emails.

Supports two authentication modes:
- Delegated (default): Uses Device Code flow - you sign in via browser
- Application: Uses Client Secret - requires admin consent

Usage:
    # Delegated mode (default) - sign in as yourself
    uv run python scripts/verify_graph_credentials.py

    # Application mode - uses client secret
    uv run python scripts/verify_graph_credentials.py --app

Required environment variables in .env:
    AZURE_TENANT_ID=your-tenant-id
    AZURE_CLIENT_ID=your-client-id
    
    # Only needed for --app mode:
    AZURE_CLIENT_SECRET=your-client-secret
    GRAPH_USER_ID=mailbox@yourdomain.com
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"[OK] {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"[ERROR] {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"[INFO] {text}")


async def verify_delegated():
    """Verify using Delegated permissions with Device Code flow."""
    
    print_header("Microsoft Graph API - Delegated Permissions")
    print_info("This mode signs in as YOU and accesses YOUR mailbox")
    
    # Check environment variables
    print_info("Checking environment variables...")
    
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    
    if not tenant_id or not client_id:
        missing = []
        if not tenant_id:
            missing.append("AZURE_TENANT_ID")
        if not client_id:
            missing.append("AZURE_CLIENT_ID")
        print_error(f"Missing environment variables: {', '.join(missing)}")
        return False
    
    print_success("Required environment variables found")
    print(f"    Tenant ID: {tenant_id[:8]}...")
    print(f"    Client ID: {client_id[:8]}...")
    
    # Import packages
    print_header("Testing Authentication")
    
    try:
        from azure.identity import DeviceCodeCredential
        print_success("azure-identity package imported")
    except ImportError:
        print_error("azure-identity package not installed")
        print_info("Run: uv add azure-identity")
        return False
    
    try:
        from msgraph import GraphServiceClient
        print_success("msgraph-sdk package imported")
    except ImportError:
        print_error("msgraph-sdk package not installed")
        print_info("Run: uv add msgraph-sdk")
        return False
    
    # Create credential with device code flow
    print_info("Creating Device Code credential...")
    print()
    print("=" * 60)
    print("  SIGN IN REQUIRED")
    print("=" * 60)
    print()
    
    try:
        credential = DeviceCodeCredential(
            tenant_id=tenant_id,
            client_id=client_id,
        )
        print_success("Credential object created")
    except Exception as e:
        print_error(f"Failed to create credential: {e}")
        return False
    
    # The token request will trigger the device code prompt
    print_info("Requesting access token (follow the instructions above)...")
    
    try:
        # Request token with specific delegated scopes
        scopes = ["https://graph.microsoft.com/Mail.Read"]
        token = credential.get_token(*scopes)
        print()
        print_success(f"Access token acquired (expires: {token.expires_on})")
    except Exception as e:
        print_error(f"Failed to acquire token: {e}")
        print_info("Make sure you:")
        print_info("  1. Added Delegated Mail.Read permission to your app")
        print_info("  2. Configured redirect URI in Authentication settings")
        print_info("  3. Enabled 'Allow public client flows' in Authentication")
        return False
    
    # Create Graph client
    print_header("Testing Graph API Access")
    
    client = GraphServiceClient(
        credentials=credential,
        scopes=["https://graph.microsoft.com/Mail.Read"],
    )
    
    # Test: List messages using /me endpoint
    print_info("Fetching YOUR messages (using /me endpoint)...")
    
    try:
        # Simple approach - get messages without complex request builder
        messages = await client.me.messages.get()
        
        if messages and messages.value:
            # Show first 5 messages
            msg_list = messages.value[:5]
            print_success(f"Successfully retrieved {len(messages.value)} messages (showing first {len(msg_list)})!")
            print_header("Recent Emails")
            
            for i, msg in enumerate(msg_list, 1):
                sender = "Unknown"
                if msg.from_ and msg.from_.email_address:
                    sender = msg.from_.email_address.address or "Unknown"
                
                read_status = "Read" if msg.is_read else "Unread"
                received = str(msg.received_date_time)[:19] if msg.received_date_time else "Unknown"
                
                print(f"{i}. [{read_status}] {received}")
                print(f"   From: {sender}")
                print(f"   Subject: {msg.subject or '(No subject)'}")
                print(f"   ID: {msg.id[:30]}...")
                print()
        else:
            print_success("API access works! (No messages found in inbox)")
            
    except Exception as e:
        error_str = str(e)
        print_error(f"Failed to fetch messages: {e}")
        
        if "Authorization_RequestDenied" in error_str:
            print_info("Permission denied. Make sure you have:")
            print_info("  1. Added Delegated Mail.Read permission to your app")
            print_info("  2. Configured Authentication settings correctly")
        elif "InvalidAuthenticationToken" in error_str:
            print_info("Authentication token is invalid")
        
        return False
    
    # Summary
    print_header("Verification Complete")
    print_success("All checks passed! Delegated permissions are working.")
    print()
    print("Your app can now access emails on behalf of signed-in users.")
    print()
    print("Next steps:")
    print("  1. Review docs/GRAPH_API_INTEGRATION_GUIDE.md")
    print("  2. Implement the GraphProvider with delegated auth")
    
    return True


async def verify_application():
    """Verify using Application permissions with Client Secret."""
    
    print_header("Microsoft Graph API - Application Permissions")
    print_info("This mode uses client secret and requires admin consent")
    
    # Check environment variables
    print_info("Checking environment variables...")
    
    required_vars = {
        "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
        "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
        "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
        "GRAPH_USER_ID": os.getenv("GRAPH_USER_ID"),
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    
    if missing:
        print_error(f"Missing environment variables: {', '.join(missing)}")
        print_info("Please add these to your .env file:")
        for var in missing:
            print(f"    {var}=your-value-here")
        return False
    
    print_success("All required environment variables found")
    print(f"    Tenant ID: {required_vars['AZURE_TENANT_ID'][:8]}...")
    print(f"    Client ID: {required_vars['AZURE_CLIENT_ID'][:8]}...")
    print(f"    User/Mailbox: {required_vars['GRAPH_USER_ID']}")
    
    # Import packages
    print_header("Testing Authentication")
    
    try:
        from azure.identity import ClientSecretCredential
        print_success("azure-identity package imported")
    except ImportError:
        print_error("azure-identity package not installed")
        print_info("Run: uv add azure-identity")
        return False
    
    try:
        from msgraph import GraphServiceClient
        print_success("msgraph-sdk package imported")
    except ImportError:
        print_error("msgraph-sdk package not installed")
        print_info("Run: uv add msgraph-sdk")
        return False
    
    # Create credential
    print_info("Creating Client Secret credential...")
    try:
        credential = ClientSecretCredential(
            tenant_id=required_vars["AZURE_TENANT_ID"],
            client_id=required_vars["AZURE_CLIENT_ID"],
            client_secret=required_vars["AZURE_CLIENT_SECRET"],
        )
        print_success("Credential object created")
    except Exception as e:
        print_error(f"Failed to create credential: {e}")
        return False
    
    # Get access token
    print_info("Acquiring access token...")
    try:
        token = credential.get_token("https://graph.microsoft.com/.default")
        print_success(f"Access token acquired (expires: {token.expires_on})")
    except Exception as e:
        print_error(f"Failed to acquire token: {e}")
        print_info("Check your AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET")
        return False
    
    # Create Graph client
    print_header("Testing Graph API Access")
    
    client = GraphServiceClient(
        credentials=credential,
        scopes=["https://graph.microsoft.com/.default"],
    )
    
    user_id = required_vars["GRAPH_USER_ID"]
    
    # Test: List messages
    print_info(f"Fetching messages from mailbox: {user_id}")
    
    try:
        from msgraph.generated.users.item.messages.messages_request_builder import (
            MessagesRequestBuilder,
        )
        
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            top=5,
            select=["id", "subject", "from", "receivedDateTime", "isRead"],
            orderby=["receivedDateTime DESC"],
        )
        
        config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )
        
        # Use /users/{id} endpoint for application permissions
        messages = await client.users.by_user_id(user_id).messages.get(
            request_configuration=config
        )
        
        if messages and messages.value:
            print_success(f"Successfully retrieved {len(messages.value)} messages!")
            print_header("Recent Emails")
            
            for i, msg in enumerate(messages.value, 1):
                sender = "Unknown"
                if msg.from_ and msg.from_.email_address:
                    sender = msg.from_.email_address.address or "Unknown"
                
                read_status = "Read" if msg.is_read else "Unread"
                received = str(msg.received_date_time)[:19] if msg.received_date_time else "Unknown"
                
                print(f"{i}. [{read_status}] {received}")
                print(f"   From: {sender}")
                print(f"   Subject: {msg.subject or '(No subject)'}")
                print(f"   ID: {msg.id[:30]}...")
                print()
        else:
            print_success("API access works! (No messages found in inbox)")
            
    except Exception as e:
        error_str = str(e)
        print_error(f"Failed to fetch messages: {e}")
        
        if "Authorization_RequestDenied" in error_str or "403" in error_str:
            print_info("Permission denied. Make sure you have:")
            print_info("  1. Added Application (not Delegated) Mail.Read permission")
            print_info("  2. Granted ADMIN CONSENT in Azure Portal")
            print_info("")
            print_info("Try running without --app flag to use Delegated mode instead:")
            print_info("  uv run python scripts/verify_graph_credentials.py")
        elif "ResourceNotFound" in error_str or "MailboxNotFound" in error_str:
            print_info(f"Mailbox not found: {user_id}")
            print_info("  Check that GRAPH_USER_ID is a valid email address")
        elif "InvalidAuthenticationToken" in error_str:
            print_info("Authentication token is invalid")
        
        return False
    
    # Summary
    print_header("Verification Complete")
    print_success("All checks passed! Application permissions are working.")
    print()
    print("Your app can access any mailbox without user sign-in.")
    
    return True


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Verify Microsoft Graph API credentials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Delegated mode (sign in as yourself):
    uv run python scripts/verify_graph_credentials.py

  Application mode (client secret, requires admin consent):
    uv run python scripts/verify_graph_credentials.py --app
        """
    )
    
    parser.add_argument(
        "--app", 
        action="store_true",
        help="Use Application permissions (client secret) instead of Delegated"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    if args.app:
        success = asyncio.run(verify_application())
    else:
        success = asyncio.run(verify_delegated())
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
