import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    print(f"Starting Flask app...")
    print(f"Debug mode: {'On' if debug_mode else 'Off'}")
    print(f"Listening on port: {port}")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
