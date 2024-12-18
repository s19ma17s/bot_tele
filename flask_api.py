from flask import Flask, request, jsonify
import os
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)


@app.route("/your-api-endpoint", methods=["POST"])
def your_api_endpoint():
    try:
        data = request.form.to_dict()
        files = request.files
        if files:
            file = files["file"]
            print("file received")
            print(file.filename)
            print(file.content_type)
        logger.info(f"Data received from telegram bot: {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error in api endpoint: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500

def run_flask_app():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
        )
    run_flask_app()