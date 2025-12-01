import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
import paramiko
from io import StringIO
import time
import socket

# ==============================================================================
# ⚠️ SECURITY WARNING ⚠️
# These are placeholders. In a real application, NEVER hardcode credentials.
# Use environment variables, a secret manager, or an SSH key pair (highly recommended).
# ==============================================================================
SSH_HOST = "YOUR_SERVER_IP" # Replace with your server IP or hostname
SSH_PORT = 22
SSH_USER = "YOUR_USERNAME"  # Replace with your SSH user
SSH_PASS = "YOUR_PASSWORD"  # Replace with your SSH password (or use keys)
# The file path specified in the request
MODSEC_RULES_PATH = "YOUR_CONFIG_PATH"
# ==============================================================================

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for flash messages

# Simple HTML template for the UI (using minimal inline CSS for aesthetics)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ModSecurity Rule Editor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f9;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .flash {
            padding: 10px;
            margin-bottom: 15px;
            border-radius: 6px;
            font-weight: bold;
        }
        .error {
            background-color: #fdd;
            color: #c00;
            border: 1px solid #c00;
        }
        .success {
            background-color: #dfd;
            color: #270;
            border: 1px solid #270;
        }
        textarea {
            width: 100%;
            height: 400px;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 6px;
            box-sizing: border-box;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
        }
        button {
            background-color: #3498db;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #2980b9;
        }
        .path-display {
            font-size: 14px;
            margin-bottom: 20px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ModSecurity Rule Editor</h1>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="path-display">
            Editing File: <strong>{{ rules_path }}</strong> (via SFTP)
        </div>

        <form method="POST" action="{{ url_for('save_rules') }}">
            <textarea name="rules_content">{{ rules_content }}</textarea>
            <button type="submit">Save Rules to Server</button>
        </form>

    </div>
</body>
</html>
"""

def get_sftp_client():
    """Establishes an SSH connection and returns an SFTP client."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # Only for testing/known hosts!
        ssh.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASS, # Consider using key_filename=... for real use
            timeout=5
        )
        sftp = ssh.open_sftp()
        return sftp, ssh
    except Exception as e:
        app.logger.error(f"SSH/SFTP Connection Error: {e}")
        flash(f'Connection Failed: {e}', 'error')
        return None, None

def read_rules_from_server():
    """Reads the content of the ModSecurity configuration file."""
    sftp, ssh = get_sftp_client()
    if not sftp:
        return f"# ERROR: Could not connect to {SSH_HOST}. Check SSH_HOST, SSH_PORT, SSH_USER, and SSH_PASS settings."

    try:
        with sftp.file(MODSEC_RULES_PATH, 'r') as remote_file:
            content = remote_file.read().decode('utf-8')
            flash('Successfully loaded rules from server.', 'success')
            return content
    except FileNotFoundError:
        flash(f'Error: Remote file not found at {MODSEC_RULES_PATH}', 'error')
        return f"# ERROR: File not found at {MODSEC_RULES_PATH}"
    except Exception as e:
        flash(f'Error reading file: {e}', 'error')
        return f"# ERROR: Failed to read file: {e}"
    finally:
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()

def write_rules_to_server(content):
    """Writes new content to the ModSecurity configuration file."""
    sftp, ssh = get_sftp_client()
    if not sftp:
        return False

    try:
        # Use StringIO to treat the string content as a file-like object
        data = StringIO(content)
        sftp.putfo(data, MODSEC_RULES_PATH)
        flash('Rules successfully saved to the server.', 'success')
        return True
    except Exception as e:
        flash(f'Error writing file: {e}', 'error')
        app.logger.error(f"SFTP Write Error: {e}")
        return False
    finally:
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()

@app.route('/', methods=['GET'])
def index():
    """Main route to display and read the current rules."""
    rules_content = read_rules_from_server()
    return render_template_string(
        HTML_TEMPLATE,
        rules_content=rules_content,
        rules_path=MODSEC_RULES_PATH
    )

@app.route('/save', methods=['POST'])
def save_rules():
    """Route to handle POST request and save the new rules."""
    new_content = request.form['rules_content']
    if write_rules_to_server(new_content):
        # Optionally, you might want to restart Nginx or ModSecurity here
        # Example of running a remote command (uncomment if needed and configured)
        # run_remote_command('sudo systemctl reload nginx')
        pass

    return redirect(url_for('index'))

if __name__ == '__main__':
    # Instructions to run the app
    # 1. Install necessary libraries: pip install flask paramiko
    # 2. Replace FAKE_... placeholders with actual server details.
    # 3. Ensure the SSH user has appropriate write permissions to the file path.
    # 4. Run the app: python app.py
    print("------------------------------------------------------------------")
    print(f"Attempting to connect to: {SSH_HOST}:{SSH_PORT} as {SSH_USER}")
    print(f"Target file path: {MODSEC_RULES_PATH}")
    print("------------------------------------------------------------------")
    print("If you see connection errors, ensure you have replaced the FAKE_...")
    print("placeholders in app.py with valid credentials and host details.")
    print("Running Flask app on http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0')
