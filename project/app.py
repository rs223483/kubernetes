from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from psycopg2 import sql, Error
from prometheus_client import start_http_server, Summary, Counter, Gauge, Histogram, generate_latest, REGISTRY
import os
import time

app = Flask(__name__)

# Define a Counter to track the number of requests
REQUEST_COUNT = Counter('custom_request_count', 'Total number of requests received', ['method', 'endpoint'])

# Define a Summary to track request duration
REQUEST_LATENCY = Summary('custom_request_latency_seconds', 'Time spent processing request', ['method', 'endpoint'])

# Define a Gauge to track in-progress requests
IN_PROGRESS = Gauge('custom_in_progress_requests', 'Number of requests in progress')

# Define a Histogram to track request duration with custom buckets
REQUEST_LATENCY_HISTOGRAM = Histogram(
    'custom_request_latency_histogram_seconds',
    'Request latency histogram',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# Decorator to track custom metrics for each request
@app.before_request
def start_request_metrics():
    request.start_time = time.time()  # Track request start time
    IN_PROGRESS.inc()  # Increment the number of in-progress requests

@app.after_request
def track_request_metrics(response):
    # Calculate request latency
    latency = time.time() - request.start_time

    # Track request count, latency, and latency in histogram
    REQUEST_COUNT.labels(request.method, request.path).inc()
    REQUEST_LATENCY.labels(request.method, request.path).observe(latency)
    REQUEST_LATENCY_HISTOGRAM.labels(request.method, request.path).observe(latency)

    # Decrement in-progress requests
    IN_PROGRESS.dec()

    return response

def create_connection():
    try:
        connection = psycopg2.connect(
            user=os.getenv('DB_USERNAME'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )
        return connection
    except Error as e:
        print("Error while connecting to PostgreSQL", e)
        return None

@app.route('/', methods=['GET'])
def index():
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM goals")
        goals = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('index.html', goals=goals)
    else:
        return "Error connecting to the PostgreSQL database", 500

@app.route('/add_goal', methods=['POST'])
def add_goal():
    goal_name = request.form.get('goal_name')
    if goal_name:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO goals (goal_name) VALUES (%s)", (goal_name,))
            connection.commit()
            cursor.close()
            connection.close()
    return redirect(url_for('index'))

@app.route('/remove_goal', methods=['POST'])
def remove_goal():
    goal_id = request.form.get('goal_id')
    if goal_id:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM goals WHERE id = %s", (goal_id,))
            connection.commit()
            cursor.close()
            connection.close()
    return redirect(url_for('index'))

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/metrics')
def metrics():
    return Response(generate_latest(REGISTRY), mimetype='text/plain')

if __name__ == '__main__':
    # start_http_server(8000)
    # Run the Flask app on port 8080
    app.run(host='0.0.0.0', port=8080)
