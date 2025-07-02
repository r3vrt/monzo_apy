import os
import json
import requests
from urllib.parse import urlparse, parse_qs
from monzo import MonzoClient

def save_credentials(client_id: str, client_secret: str, redirect_uri: str):
    """Save credentials to the existing auth.json file."""
    config_dir = "config"
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    auth_file = os.path.join(config_dir, "auth.json")
    
    # Load existing auth data if it exists
    auth_data = {}
    if os.path.exists(auth_file):
        try:
            with open(auth_file, 'r') as f:
                auth_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    # Update with new credentials
    auth_data.update({
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri
    })
    
    with open(auth_file, 'w') as f:
        json.dump(auth_data, f, indent=2)
    print(f"Credentials saved to {auth_file}")

def load_credentials():
    """Load credentials from existing auth.json file if they exist."""
    auth_file = os.path.join("config", "auth.json")
    if os.path.exists(auth_file):
        try:
            with open(auth_file, 'r') as f:
                auth_data = json.load(f)
                # Check if we have the required credentials
                if all(key in auth_data for key in ["client_id", "client_secret", "redirect_uri"]):
                    return auth_data
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return None

def main():
    print("=== Monzo OAuth Authentication Flow ===")
    
    # Try to load existing credentials
    saved_credentials = load_credentials()
    if saved_credentials:
        print("Found saved credentials. Use them? (y/n): ", end="")
        use_saved = input().lower().strip() == 'y'
        if use_saved:
            client_id = saved_credentials["client_id"]
            client_secret = saved_credentials["client_secret"]
            redirect_uri = saved_credentials["redirect_uri"]
            print("Using saved credentials.")
        else:
            client_id = None
            client_secret = None
            redirect_uri = None
    else:
        client_id = None
        client_secret = None
        redirect_uri = None
    
    # Get client credentials from env, saved file, or prompt
    client_id = os.getenv("MONZO_CLIENT_ID") or client_id or input("Enter your Monzo client_id: ")
    client_secret = os.getenv("MONZO_CLIENT_SECRET") or client_secret or input("Enter your Monzo client_secret: ")
    redirect_uri = os.getenv("MONZO_REDIRECT_URI") or redirect_uri or input("Enter your redirect_uri: ")

    # Save credentials before proceeding
    save_credentials(client_id, client_secret, redirect_uri)

    client = MonzoClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    # Step 1: Generate and show the authorization URL
    auth_url = client.get_authorization_url()
    print("\nGo to this URL in your browser and authorize the app:")
    print(auth_url)
    print("\n⚠️  IMPORTANT: After clicking the link, you may need to approve access in your Monzo app!")
    print("   - Check your phone for a Monzo app notification")
    print("   - Or open the Monzo app and look for a pending authorization request")
    print("   - Approve the request to continue with the authentication flow")
    print()

    # Step 2: User pastes the full redirect URL
    redirect_url = input("Paste the full redirect URL you were sent to: ").strip()
    parsed = urlparse(redirect_url)
    code = parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        print("Could not find ?code=... in the URL. Please try again.")
        return

    # Step 3: Exchange code for tokens
    try:
        tokens = client.exchange_code_for_token(code)
        print("\nAccess token:", tokens["access_token"])
        print("Refresh token:", tokens.get("refresh_token"))

        # Step 4: Save tokens for future use
        client.save_auth()  # Saves to config/auth.json by default
        print("\nTokens saved to config/auth.json. You can now use the library without re-authenticating.")
    except requests.exceptions.HTTPError as e:
        print(f"\nError exchanging code for token: {e}")
        try:
            error_data = e.response.json()
            print(f"Error details: {json.dumps(error_data, indent=2)}")
        except:
            print(f"Response text: {e.response.text}")
        return
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return

if __name__ == "__main__":
    main() 