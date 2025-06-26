from flask import Flask, request, jsonify, redirect
import hashlib
import base64
import sqlite3
from datetime import datetime

# Create a Flask app (this is the web server)
app = Flask(__name__)

# Set up SQLite database to store URLs
conn = sqlite3.connect('urls.db', check_same_thread=False)  # Creates a file called urls.db
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS urls
                 (short_code TEXT PRIMARY KEY, long_url TEXT, clicks INTEGER, last_accessed TEXT)''')
conn.commit()  # Save the database changes

# Root route (shows info when you visit http://127.0.0.1:5055/)
@app.route('/')
def home():
    return jsonify({
        "message": "Welcome to the URL Shortener Microservice",
        "endpoints": {
            "POST /shorten": "Create a short URL from a long URL",
            "GET /stats/<short_code>": "Retrieve statistics for a short URL",
            "GET /<short_code>": "Redirect to the original URL"
        }
    })

# Function to create a short code from a long URL
def generate_short_code(long_url):
    hash_object = hashlib.md5(long_url.encode())  # Hash the URL to make it unique
    short_code = base64.urlsafe_b64encode(hash_object.digest()).decode()[:6]  # Take first 6 characters
    return short_code

# Endpoint to create a short URL
@app.route('/shorten', methods=['POST'])
def create_short_url():
    data = request.get_json()  # Get the JSON data sent in the request
    long_url = data.get('url')  # Get the 'url' field
    if not long_url:
        return jsonify({"error": "URL is required"}), 400  # Error if no URL provided
    
    # Check if URL starts with http:// or https://
    if not long_url.startswith(('http://', 'https://')):
        return jsonify({"error": "Invalid URL format"}), 400
    
    short_code = generate_short_code(long_url)  # Generate short code
    cursor.execute("SELECT short_code FROM urls WHERE short_code = ?", (short_code,))
    if cursor.fetchone():  # Check if short code already exists
        return jsonify({"error": "Short code collision, try again"}), 409
    
    # Save the URL to the database
    cursor.execute("INSERT INTO urls (short_code, long_url, clicks, last_accessed) VALUES (?, ?, ?, ?)",
                  (short_code, long_url, 0, None))
    conn.commit()
    
    short_url = f"https://short.ly/{short_code}"
    return jsonify({"short_url": short_url}), 201  # Return the short URL

# Endpoint to get statistics for a short URL
@app.route('/stats/<short_code>', methods=['GET'])
def get_stats(short_code):
    cursor.execute("SELECT long_url, clicks, last_accessed FROM urls WHERE short_code = ?", (short_code,))
    result = cursor.fetchone()
    if not result:
        return jsonify({"error": "Short URL not found"}), 404  # Error if short code not found
    
    long_url, clicks, last_accessed = result
    return jsonify({
        "short_url": f"https://short.ly/{short_code}",
        "long_url": long_url,
        "clicks": clicks,
        "last_accessed": last_accessed
    })

# Endpoint to redirect from short URL to long URL
@app.route('/<short_code>')
def redirect_url(short_code):
    cursor.execute("SELECT long_url, clicks, last_accessed FROM urls WHERE short_code = ?", (short_code,))
    result = cursor.fetchone()
    if not result:
        return jsonify({"error": "Short URL not found"}), 404
    
    long_url, clicks, _ = result
    # Update click count and last accessed time
    cursor.execute("UPDATE urls SET clicks = ?, last_accessed = ? WHERE short_code = ?",
                  (clicks + 1, datetime.utcnow().isoformat(), short_code))
    conn.commit()
    return redirect(long_url, code=302)  # Redirect to the original URL

if __name__ == '__main__':
    app.run(debug=True)  # Start the server