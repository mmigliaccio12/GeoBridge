#!/usr/bin/env python3
import os
from app import app

if __name__ == '__main__':
    # Get port from environment variable (Railway sets this automatically)
    port = int(os.environ.get('PORT', 5001))
    
    # Disable debug mode in production
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 