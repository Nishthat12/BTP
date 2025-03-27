FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y     python3     python3-pip     nginx     curl     wget     net-tools     iproute2     iputils-ping     && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install flask zfec numpy requests

# Set up the web server
COPY index.html /var/www/html/
COPY dash.all.min.js /var/www/html/
COPY player.js /var/www/html/
COPY proxy.py /app/

# Expose port 80 for the web server
EXPOSE 80

# Start the proxy and nginx
CMD ["sh", "-c", "python3 /app/proxy.py & nginx -g 'daemon off;'"]
