import os
from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import paramiko
from io import StringIO
import time
import socket

# ==============================================================================
# ⚠️ SECURITY WARNING ⚠️
# Hardcoded credentials have been REMOVED and replaced with user input via login.
# ==============================================================================
SSH_HOST = "YOUR_SERVER_IP"  # Replace with your server IP or hostname
SSH_PORT = 22
# The file path specified in the request
MODSEC_RULES_PATH = "YOUR_RULE_PATH"
# ==============================================================================

app = Flask(__name__)
# This secret key is ESSENTIAL for Flask sessions to work securely.
app.secret_key = os.urandom(24)

# --- HTML Templates ---

# Simple HTML template for the UI (main editor page)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ModSecurity Rule Editor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .flash { padding: 10px; margin-bottom: 15px; border-radius: 6px; font-weight: bold; }
        .error { background-color: #fdd; color: #c00; border: 1px solid #c00; }
        .success { background-color: #dfd; color: #270; border: 1px solid #270; }
        textarea { width: 100%; height: 400px; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; font-family: 'Consolas', 'Courier New', monospace; font-size: 14px; }
        button { background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; }
        button:hover { background-color: #2980b9; }
        .path-display { font-size: 14px; margin-bottom: 20px; color: #555; }
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
            Editing File: <strong>{{ rules_path }}</strong> (via SFTP to {{ session.ssh_user }}@{{ ssh_host }})
        </div>

        <form method="POST" action="{{ url_for('save_rules') }}">
            <textarea name="rules_content">{{ rules_content }}</textarea>
            <button type="submit">Save Rules to Server</button>
        </form>
        <br>
        <form method="POST" action="{{ url_for('logout') }}">
            <button type="submit" style="background-color: #e74c3c;">Logout</button>
        </form>

    </div>
</body>
</html>
"""

# New HTML Template for the Login Page
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Modsecurity Editor</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); width: 300px; text-align: center; }
        h1 { color: #2c3e50; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        button { background-color: #3498db; color: white; padding: 12px 15px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; width: 100%; transition: background-color 0.3s; }
        button:hover { background-color: #2980b9; }
        .flash { padding: 10px; margin-bottom: 15px; border-radius: 6px; font-weight: bold; background-color: #fdd; color: #c00; border: 1px solid #c00; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>Login</h1>
        <p>Connect to: <strong>{{ ssh_host }}:{{ ssh_port }}</strong></p>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" action="{{ url_for('login') }}">
            <input type="text" name="username" placeholder="SFTP Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Connect & Edit Rules</button>
        </form>
    </div>
</body>
</html>
"""

# --- Core SFTP Functions ---

def get_sftp_client():
    """Establishes an SSH connection and returns an SFTP client using session credentials."""
    ssh_user = session.get('ssh_user')
    ssh_pass = session.get('ssh_pass')

    if not ssh_user or not ssh_pass:
        flash('Login credentials missing. Please log in.', 'error')
        return None, None

    try:
        ssh = paramiko.SSHClient()
        # NOTE: Using AutoAddPolicy is DANGEROUS for production systems.
        # Use WarningPolicy or load known hosts file.
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=ssh_user,
            password=ssh_pass,
            timeout=5
        )
        sftp = ssh.open_sftp()
        return sftp, ssh
    except Exception as e:
        app.logger.error(f"SSH/SFTP Connection Error: {e}")
        # Clear session on connection failure to force a re-login
        flash(f'Connection Failed for user {ssh_user}: {e}', 'error')
        session.pop('ssh_user', None)
        session.pop('ssh_pass', None)
        return None, None

def read_rules_from_server():
    """Reads the content of the ModSecurity configuration file."""
    sftp, ssh = get_sftp_client()
    if not sftp:
        return f"# ERROR: Could not establish connection to {SSH_HOST}. Please refresh and log in again."

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

# --- Flask Routes ---

@app.route('/', methods=['GET'])
def index():
    """Main route to display and read the current rules. Requires login."""
    if 'ssh_user' not in session or 'ssh_pass' not in session:
        flash('Please log in to edit the ModSecurity rules.', 'error')
        return redirect(url_for('login'))

    rules_content = read_rules_from_server()
    return render_template_string(
        HTML_TEMPLATE,
        rules_content=rules_content,
        rules_path=MODSEC_RULES_PATH,
        ssh_host=SSH_HOST # Pass to template for display
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles the user login form and stores credentials in the session."""
    if request.method == 'POST':
        # Store credentials in session
        session['ssh_user'] = request.form['username']
        session['ssh_pass'] = request.form['password']

        # Test connection immediately
        sftp, ssh = get_sftp_client()
        if sftp:
            sftp.close()
            ssh.close()
            flash('Login successful. Loading rules.', 'success')
            return redirect(url_for('index'))
        else:
            # get_sftp_client already flashed the error message
            # The session was cleared inside get_sftp_client on failure
            return redirect(url_for('login')) # Redirect back to login on failure

    # GET request
    return render_template_string(
        LOGIN_TEMPLATE,
        ssh_host=SSH_HOST,
        ssh_port=SSH_PORT
    )

@app.route('/logout', methods=['POST'])
def logout():
    """Clears the session and redirects to the login page."""
    session.pop('ssh_user', None)
    session.pop('ssh_pass', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/save', methods=['POST'])
def save_rules():
    """Route to handle POST request and save the new rules."""
    if 'ssh_user' not in session:
        flash('Session expired or not logged in.', 'error')
        return redirect(url_for('login'))

    new_content = request.form['rules_content']
    write_rules_to_server(new_content)

    # You may want to add logic here to run a remote command
    # to restart or reload your Nginx/ModSecurity service after saving.

    return redirect(url_for('index'))

if __name__ == '__main__':
    print("------------------------------------------------------------------")
    print(f"Target SFTP Host: {SSH_HOST}:{SSH_PORT}")
    print(f"Target File Path: {MODSEC_RULES_PATH}")
    print("------------------------------------------------------------------")
    print("Running Flask app on http://127.0.0.1:5000")
    print("Please navigate to this URL and log in to connect to the server.")
    app.run(debug=True, host='0.0.0.0')
