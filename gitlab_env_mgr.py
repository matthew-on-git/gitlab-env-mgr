#!/usr/bin/env python3
"""
GitLab Environment Variable Manager with SSL options

Enhanced version with SSL certificate handling for self-hosted GitLab instances.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
import urllib3
from dotenv import load_dotenv

# Constants
GITLAB_API_VERSION = "v4"
DEFAULT_ENV_FILE = "gitlab.env"
LOG_FILE = "gitlab_env_mgr.log"


class SSLConfig:
    """SSL configuration for GitLab API requests."""

    def __init__(self, verify_ssl: bool = True, ca_bundle: Optional[str] = None):
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle

        # Setup SSL verification
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.verify = False
        elif ca_bundle:
            self.verify = ca_bundle
        else:
            self.verify = True

    def get_verify_setting(self):
        """Get the SSL verification setting for requests."""
        return self.verify

    def is_ssl_verification_enabled(self):
        """Check if SSL verification is enabled."""
        return self.verify_ssl


class GitLabConfig:
    """Configuration for GitLab API connection."""

    def __init__(self, base_url: str, token: str, project_id: str,
                 ssl_config: Optional[SSLConfig] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.project_id = project_id
        self.ssl_config = ssl_config or SSLConfig()

    def get_api_url(self) -> str:
        """Get the full API URL for the project."""
        return f"{self.base_url}/api/{GITLAB_API_VERSION}/projects/{self.project_id}/variables"

    def get_headers(self) -> Dict[str, str]:
        """Get the headers for API requests."""
        return {"PRIVATE-TOKEN": self.token}


class GitLabVariableManager:
    """Manages GitLab CI/CD variables via API with SSL options"""

    def __init__(self, config: GitLabConfig):
        self.base_url = config.base_url
        self.project_id = config.project_id
        self.api_url = config.get_api_url()

        # Setup session
        self.session = requests.Session()
        self.session.headers.update(config.get_headers())
        self.session.verify = config.ssl_config.get_verify_setting()

        # Setup logging
        self.logger = logging.getLogger('GitLabVariableManager')

    def get_all_variables(self) -> List[Dict]:
        """Fetch all variables from GitLab project"""
        self.logger.info("Fetching variables from project %s", self.project_id)

        try:
            response = self.session.get(self.api_url)
            response.raise_for_status()
            variables = response.json()
            self.logger.info("Retrieved %d variables", len(variables))
            return variables
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to fetch variables: %s", e)
            raise

    def create_variable(self, variable: Dict) -> bool:
        """Create a new variable"""
        self.logger.info("Creating variable: %s", variable['key'])

        data = {
            "key": variable["key"],
            "value": variable.get("value", ""),
            "protected": variable.get("protected", False),
            "masked": variable.get("masked", False),
            "variable_type": variable.get("variable_type", "env_var")
        }

        # Add description as a comment in the value if provided
        if "description" in variable and variable["description"]:
            data["description"] = variable["description"]

        try:
            response = self.session.post(self.api_url, json=data)
            response.raise_for_status()
            self.logger.info("Successfully created variable: %s", variable['key'])
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to create variable %s: %s", variable['key'], e)
            return False

    def update_variable(self, variable: Dict) -> bool:
        """Update an existing variable"""
        self.logger.info("Updating variable: %s", variable['key'])

        url = f"{self.api_url}/{variable['key']}"
        data = {
            "value": variable.get("value", ""),
            "protected": variable.get("protected", False),
            "masked": variable.get("masked", False),
            "variable_type": variable.get("variable_type", "env_var")
        }

        try:
            response = self.session.put(url, json=data)
            response.raise_for_status()
            self.logger.info("Successfully updated variable: %s", variable['key'])
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to update variable %s: %s", variable['key'], e)
            return False

    def delete_variable(self, key: str) -> bool:
        """Delete a variable"""
        self.logger.info("Deleting variable: %s", key)

        url = f"{self.api_url}/{key}"

        try:
            response = self.session.delete(url)
            response.raise_for_status()
            self.logger.info("Successfully deleted variable: %s", key)
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to delete variable %s: %s", key, e)
            return False

    def export_variables(self, output_file: str, include_masked: bool = False) -> None:
        """Export variables to JSON file"""
        self.logger.info("Exporting variables to %s", output_file)

        variables = self.get_all_variables()

        # Format variables for export
        export_data = {
            "variables": [],
            "metadata": {
                "project_id": self.project_id,
                "exported_at": datetime.now().isoformat(),
                "total_variables": len(variables),
                "gitlab_url": self.base_url
            }
        }

        for var in variables:
            export_var = {
                "key": var["key"],
                "value": var["value"] if not var.get("masked", False) or include_masked else "",
                "protected": var.get("protected", False),
                "masked": var.get("masked", False),
                "variable_type": var.get("variable_type", "env_var"),
                "description": (
                    "Masked value not exported"
                    if var.get("masked", False) and not include_masked else "")
            }
            export_data["variables"].append(export_var)

        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        self.logger.info("Successfully exported %d variables", len(variables))

    def import_variables(self, input_file: str, force: bool = False) -> None:
        """Import variables from JSON file"""
        self.logger.info("Importing variables from %s", input_file)

        # Load variables from file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if "variables" not in data:
            raise ValueError("Invalid format: 'variables' key not found in JSON")

        import_vars = data["variables"]
        current_vars = {v["key"]: v for v in self.get_all_variables()}

        created = 0
        updated = 0
        skipped = 0
        failed = 0

        for var in import_vars:
            # Skip if value is empty and it's a masked variable (unless force)
            if not var.get("value") and var.get("masked") and not force:
                self.logger.warning("Skipping masked variable with empty value: %s", var['key'])
                skipped += 1
                continue

            if var["key"] in current_vars:
                # Update existing
                if self.update_variable(var):
                    updated += 1
                else:
                    failed += 1
            else:
                # Create new
                if self.create_variable(var):
                    created += 1
                else:
                    failed += 1

        self.logger.info(
            "Import complete: %d created, %d updated, %d skipped, %d failed",
            created, updated, skipped, failed)

    def diff_variables(self, input_file: str) -> None:
        """Show differences between current and file variables"""
        self.logger.info("Comparing current variables with %s", input_file)

        # Load variables from file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        file_vars = {v["key"]: v for v in data.get("variables", [])}
        current_vars = {v["key"]: v for v in self.get_all_variables()}

        # Find differences
        all_keys = set(file_vars.keys()) | set(current_vars.keys())

        added = []
        removed = []
        modified = []

        for key in sorted(all_keys):
            if key in file_vars and key not in current_vars:
                added.append(key)
            elif key in current_vars and key not in file_vars:
                removed.append(key)
            elif key in file_vars and key in current_vars:
                # Check if values differ
                file_var = file_vars[key]
                current_var = current_vars[key]

                if (file_var.get("value") != current_var.get("value") or
                    file_var.get("protected") != current_var.get("protected") or
                    file_var.get("masked") != current_var.get("masked") or
                    file_var.get("variable_type") != current_var.get("variable_type")):
                    modified.append(key)

        # Print diff summary
        print("\n=== Variable Differences ===")
        print(f"Added:    {len(added)}")
        print(f"Removed:  {len(removed)}")
        print(f"Modified: {len(modified)}")

        if added:
            print("\nVariables to add:")
            for key in added:
                print(f"  + {key}")

        if removed:
            print("\nVariables to remove:")
            for key in removed:
                print(f"  - {key}")

        if modified:
            print("\nVariables to modify:")
            for key in modified:
                print(f"  ~ {key}")

    def push_variables(self, input_file: str) -> None:
        """Push variables (sync with file, removing extras)"""
        self.logger.info("Pushing variables from %s", input_file)

        # Load variables from file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        file_vars = {v["key"]: v for v in data.get("variables", [])}
        current_vars = {v["key"]: v for v in self.get_all_variables()}

        # Delete variables not in file
        for key in current_vars:
            if key not in file_vars:
                self.delete_variable(key)

        # Import all variables from file
        self.import_variables(input_file, force=True)

def setup_logging(verbose: bool, log_file: Optional[str] = None):
    """Configure logging"""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)

    # File handler
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(level=log_level, handlers=handlers)

def main():
    """Main entry point for the GitLab Environment Variable Manager."""
    parser = argparse.ArgumentParser(
        description="GitLab CI/CD Variable Manager with SSL support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Export all variables:
    %(prog)s -p 12345 -o variables.json

  Export with self-signed certificate:
    %(prog)s -p 12345 -o variables.json --no-verify-ssl

  Import variables:
    %(prog)s -p 12345 -i variables.json

  Show differences:
    %(prog)s -p 12345 -d variables.json

  Push variables (sync):
    %(prog)s -p 12345 --push variables.json

  Using custom CA certificate:
    %(prog)s -p 12345 -o variables.json --ca-bundle /path/to/ca-cert.pem
"""
    )

    # Authentication
    parser.add_argument(
        '-e', '--env-file', default=DEFAULT_ENV_FILE,
        help=f'Environment file with GITLAB_URL and GITLAB_TOKEN '
             f'(default: {DEFAULT_ENV_FILE})')
    parser.add_argument('-u', '--gitlab-url', help='GitLab URL (overrides env file)')
    parser.add_argument('-t', '--token', help='GitLab personal access token (overrides env file)')

    # Project
    parser.add_argument('-p', '--project-id', required=True,
                        help='GitLab project ID or path (e.g., 12345 or group/project)')

    # Operations (mutually exclusive)
    ops = parser.add_mutually_exclusive_group(required=True)
    ops.add_argument('-o', '--export', metavar='FILE',
                     help='Export variables to JSON file')
    ops.add_argument('-i', '--import', metavar='FILE', dest='import_file',
                     help='Import variables from JSON file')
    ops.add_argument('-d', '--diff', metavar='FILE',
                     help='Show differences between current and file variables')
    ops.add_argument('--push', metavar='FILE',
                     help='Push variables from file (sync, removes extras)')

    # SSL Options
    ssl_group = parser.add_argument_group('SSL options')
    ssl_group.add_argument('--no-verify-ssl', action='store_true',
                          help='Disable SSL certificate verification (use for self-signed certs)')
    ssl_group.add_argument('--ca-bundle', metavar='PATH',
                          help='Path to CA certificate bundle file')

    # Options
    parser.add_argument('--include-masked', action='store_true',
                        help='Include masked variable values in export (CAUTION: exposes secrets)')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Force import of variables with empty values')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('-l', '--log-file', default=LOG_FILE,
                        help=f'Log file path (default: {LOG_FILE})')

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger('main')

    # Load environment
    env_path = Path(args.env_file)
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded environment from %s", env_path)

    # Get GitLab URL and token
    gitlab_url = args.gitlab_url or os.getenv('GITLAB_URL')
    token = args.token or os.getenv('GITLAB_TOKEN')

    if not gitlab_url or not token:
        logger.error("GitLab URL and token are required. Set via arguments or environment file.")
        sys.exit(1)

    # SSL configuration warning
    if args.no_verify_ssl:
        logger.warning("SSL certificate verification is disabled. This is insecure!")

    # Create manager with SSL options
    try:
        ssl_config = SSLConfig(
            verify_ssl=not args.no_verify_ssl,
            ca_bundle=args.ca_bundle
        )
        config = GitLabConfig(
            gitlab_url,
            token,
            args.project_id,
            ssl_config=ssl_config
        )
        manager = GitLabVariableManager(config)

        # Execute operation
        if args.export:
            manager.export_variables(args.export, args.include_masked)
        elif args.import_file:
            manager.import_variables(args.import_file, args.force)
        elif args.diff:
            manager.diff_variables(args.diff)
        elif args.push:
            manager.push_variables(args.push)

    except (requests.exceptions.RequestException, ValueError, FileNotFoundError) as e:
        logger.error("Operation failed: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
