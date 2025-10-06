# GitLab Environment Variable Manager

A Python utility for managing GitLab CI/CD variables through the GitLab API. Export, import, diff, and sync project variables with ease.

## Features

- 📤 **Export** CI/CD variables to JSON format
- 📥 **Import** variables from JSON files
- 🔍 **Diff** to compare current variables with a file
- 🔄 **Push** (sync) variables, removing any not in the file
- 🔒 **Secure** handling of masked/protected variables
- 📁 **File variable** support for multi-line content
- 🏷️ **Metadata** tracking for exports

## Installation

1. Clone the repository:
```bash
git clone https://github.com/matthew-on-git/gitlab-env-mgr.git
cd gitlab-env-mgr
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure authentication:
```bash
cp gitlab.env.example gitlab.env
# Edit gitlab.env with your GitLab URL and token
```

## Configuration

### Personal Access Token

Create a personal access token in GitLab:

1. Go to your GitLab instance (e.g., `https://gitlab.com/-/profile/personal_access_tokens`)
2. Create a new token with `api` scope
3. Save the token in your `gitlab.env` file

### Environment File

The `gitlab.env` file should contain:

```bash
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your-personal-access-token-here
```

## Usage

### Export Variables

Export all variables from a project (masked values hidden by default):

```bash
./gitlab-env-mgr.py -p PROJECT_ID -o variables.json
```

Export with masked values (⚠️ CAUTION: This exposes secrets):

```bash
./gitlab-env-mgr.py -p PROJECT_ID -o variables.json --include-masked
```

### Import Variables

Import variables from a JSON file:

```bash
./gitlab-env-mgr.py -p PROJECT_ID -i variables.json
```

Force import (including empty values):

```bash
./gitlab-env-mgr.py -p PROJECT_ID -i variables.json --force
```

### Compare Variables

Show differences between current project variables and a file:

```bash
./gitlab-env-mgr.py -p PROJECT_ID -d variables.json
```

### Sync Variables

Push variables from file, removing any not in the file:

```bash
./gitlab-env-mgr.py -p PROJECT_ID --push variables.json
```

### Project ID

The project ID can be:
- Numeric ID: `12345`
- Full path: `group/subgroup/project`

## JSON Format

The tool uses the following JSON structure:

```json
{
  "variables": [
    {
      "key": "VARIABLE_NAME",
      "value": "variable_value",
      "description": "Optional description",
      "protected": true,
      "masked": false,
      "variable_type": "env_var"
    },
    {
      "key": "SSH_KEY",
      "value": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
      "description": "SSH private key",
      "protected": true,
      "masked": true,
      "variable_type": "file"
    }
  ],
  "metadata": {
    "project_id": "group/project",
    "exported_at": "2024-01-01T12:00:00",
    "total_variables": 2,
    "gitlab_url": "https://gitlab.com"
  }
}
```

### Variable Properties

- `key`: Variable name (required)
- `value`: Variable value (empty for masked variables on export)
- `description`: Optional description (GitLab doesn't store this, but useful for documentation)
- `protected`: Boolean - Only exposed on protected branches/tags
- `masked`: Boolean - Hidden in job logs (requires specific format)
- `variable_type`: Either `"env_var"` (default) or `"file"`

### Masked Variable Requirements

For a variable to be maskable in GitLab:
- Minimum 8 characters long
- Only contains letters, numbers, and underscores
- No leading/trailing whitespace

## Examples

### Backup Current Variables

```bash
./gitlab-env-mgr.py -p mygroup/myproject -o backup.json
```

### Migrate Variables Between Projects

```bash
# Export from source project
./gitlab-env-mgr.py -p source-project -o variables.json

# Import to destination project
./gitlab-env-mgr.py -p dest-project -i variables.json
```

### Update Multiple Variables

```bash
# Export current
./gitlab-env-mgr.py -p myproject -o current.json

# Edit current.json with your changes

# Check what will change
./gitlab-env-mgr.py -p myproject -d current.json

# Apply changes
./gitlab-env-mgr.py -p myproject -i current.json
```

## Security Considerations

1. **Masked Variables**: By default, masked variable values are not exported to prevent accidental exposure
2. **File Storage**: Store exported JSON files securely, especially if using `--include-masked`
3. **Version Control**: Add `gitlab.env` and sensitive JSON files to `.gitignore`
4. **Access Tokens**: Use tokens with minimal required permissions and rotate regularly

## Logging

The tool provides detailed logging:
- Use `-v` or `--verbose` for debug output
- Logs are written to `gitlab_env_mgr.log` by default
- Specify custom log file with `-l` or `--log-file`

## Error Handling

Common issues and solutions:

### 401 Unauthorized
- Verify your personal access token is valid
- Ensure the token has `api` scope
- Check the GitLab URL is correct

### 404 Not Found
- Verify the project ID or path
- Ensure you have access to the project
- Try using the numeric project ID

### Variable Not Updating
- Check if the variable is protected (only available on protected branches)
- Verify the JSON format is correct
- Use `--force` flag to update variables with empty values

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Related Projects

- [bitbucket-env-mgr](https://github.com/matthew-on-git/bitbucket-env-mgr) - Similar tool for Bitbucket

## Author

Matthew Mellor