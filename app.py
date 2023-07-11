import subprocess
import logging
from flask import Flask, request, send_file

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/upload', methods=['POST', 'GET'])
def upload_file():
    if request.method == 'POST':
        # Handle POST request for uploading the file
        if 'image' in request.files:
            image_file = request.files['image']
            image_path = '/app/image.jpg'
            image_file.save(image_path)

            # Scan the uploaded file for viruses using clamscan
            scan_command = ['clamscan', image_path]
            result = subprocess.run(scan_command, capture_output=True, text=True)

            if result.returncode == 0:
                # File is clean, further processing
                # Log the scan result
                logging.info(f"Scan result for {image_path}:\n{result.stdout}")

                # Return success response
                return 'File uploaded successfully'
            else:
                # File is infected or an error occurred
                # Log the scan result
                logging.warning(f"Scan result for {image_path}:\n{result.stderr}")

                return 'File is infected or an error occurred'

        else:
            return 'No image received'
    elif request.method == 'GET':
        # Handle GET request to retrieve the cleared image
        image_path = '/app/image.jpg'

        # Return the cleared image file
        return send_file(image_path, mimetype='image/jpeg')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
