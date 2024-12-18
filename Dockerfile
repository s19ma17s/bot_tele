FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of your project files
COPY . .

# Expose the port for the web app if needed
EXPOSE 5000
# Run the application
CMD ["python", "main.py"]