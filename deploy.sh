#!/bin/bash
# Deploy script for syllabushelper.net
# Run on the server after uploading the tar.gz

set -e

echo "=== Syllabus Helper Deployment ==="

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install docker-compose plugin if not present
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# Setup project directory
PROJECT_DIR=/opt/syllabus-helper
mkdir -p $PROJECT_DIR
cp -r . $PROJECT_DIR/
cd $PROJECT_DIR

# Generate JWT secret if not set
if grep -q "CHANGE_ME" .env.production 2>/dev/null; then
    JWT=$(openssl rand -hex 32)
    sed -i "s/CHANGE_ME_TO_A_RANDOM_64_CHAR_STRING/$JWT/" .env.production
    echo "Generated JWT secret."
fi

# Copy env
cp .env.production .env

# Build and start
echo "Building containers..."
docker compose build --no-cache

echo "Starting services..."
docker compose up -d

echo ""
echo "=== Deployment complete ==="
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:80"
echo ""
echo "Next steps:"
echo "1. Setup nginx reverse proxy with SSL for syllabushelper.net"
echo "2. Run: certbot --nginx -d syllabushelper.net"
echo ""

# Setup host nginx for SSL (if nginx is installed on host)
if command -v nginx &> /dev/null; then
    echo "Setting up host nginx for syllabushelper.net..."
    cat > /etc/nginx/conf.d/syllabushelper.conf << 'NGINX'
server {
    listen 80;
    server_name syllabushelper.net www.syllabushelper.net;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        client_max_body_size 20M;
    }
}
NGINX
    nginx -t && nginx -s reload
    echo "Nginx configured. Now run: certbot --nginx -d syllabushelper.net"
fi
