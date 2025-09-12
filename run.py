# run.py  (dev entrypoint)
import os
from dotenv import load_dotenv
from health_app import create_app
import logging
logging.basicConfig(level=logging.INFO)

# Load env (.env + instance/config.py etc.)
load_dotenv()

app = create_app()

if __name__ == "__main__":
    # Configure via environment variables
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")

    app.run(host=host, port=port, debug=debug)
