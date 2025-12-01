# ---------------------------------
# Build & Run (Standalone Application)
# ---------------------------------
build:
* docker build -t modsec-editor:latest .

run:
* docker run -d -p 5000:5000 --name modsec-editor modsec-editor
