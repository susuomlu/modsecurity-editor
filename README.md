# Edit config files
In app.py change below parameter:

* SSH_HOST = "YOUR_IP"  # Replace with your server IP or hostname
* SSH_PORT = 22
* MODSEC_RULES_PATH = "YOUR_CONFIG_PATH"

# Build & Run (Standalone Application)

build:
* docker build -t modsec-editor:latest .

run:
* docker run -d -p 5000:5000 --name modsec-editor modsec-editor



