import os
from flask import Flask

# Initialize Flask app
app = Flask(__name__)

# Read the environment variable for port
port = int(os.getenv('SERVER_PORT', 8080))

@app.route('/')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
