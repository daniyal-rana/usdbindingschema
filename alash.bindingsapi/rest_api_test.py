#!/usr/bin/env python3
"""
REST API test server for testing HTTP request bindings.
This simulates a device status API that the USD bindings can poll.

To use:
1. Install Flask: pip install flask
2. Run this script: python rest_api_test.py
3. Test endpoints at http://localhost:5000
"""

import json
import time
import random
from flask import Flask, jsonify
import threading

app = Flask(__name__)

# Simulated device data
devices = {
    "aircon3245": {
        "status": "running",
        "temperature": 22.5,
        "power_consumption": 1200,
        "filter_status": "clean",
        "last_maintenance": "2024-07-15",
        "runtime_hours": 2847
    },
    "aircon9876": {
        "status": "idle", 
        "temperature": 24.1,
        "power_consumption": 150,
        "filter_status": "needs_replacement",
        "last_maintenance": "2024-06-20",
        "runtime_hours": 3241
    }
}

# Simulate changing values
def update_device_data():
    """Background thread to update device data periodically."""
    while True:
        for device_id in devices:
            device = devices[device_id]
            
            # Randomly update temperature
            device["temperature"] = round(device["temperature"] + random.uniform(-0.5, 0.5), 1)
            
            # Randomly change status
            if random.random() < 0.1:  # 10% chance
                statuses = ["running", "idle", "maintenance", "error"]
                device["status"] = random.choice(statuses)
            
            # Update power based on status
            if device["status"] == "running":
                device["power_consumption"] = random.randint(1000, 1500)
            elif device["status"] == "idle":
                device["power_consumption"] = random.randint(100, 200)
            else:
                device["power_consumption"] = 0
            
            # Increment runtime if running
            if device["status"] == "running":
                device["runtime_hours"] += 0.1
                
        time.sleep(5)  # Update every 5 seconds

@app.route('/')
def index():
    """API documentation endpoint."""
    return jsonify({
        "message": "Device Status API Test Server",
        "version": "1.0",
        "endpoints": {
            "/devices": "List all devices",
            "/devices/<device_id>": "Get specific device info",
            "/devices/<device_id>/status": "Get device status only",
            "/devices/<device_id>/temperature": "Get device temperature only"
        },
        "example_urls": [
            "http://localhost:5000/devices/aircon3245",
            "http://localhost:5000/devices/aircon3245/status",
            "http://localhost:5000/devices/aircon3245/temperature"
        ]
    })

@app.route('/devices')
def list_devices():
    """List all available devices."""
    return jsonify({
        "devices": list(devices.keys()),
        "count": len(devices),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    })

@app.route('/devices/<device_id>')
def get_device(device_id):
    """Get complete device information."""
    if device_id not in devices:
        return jsonify({"error": "Device not found"}), 404
    
    device_data = devices[device_id].copy()
    device_data["device_id"] = device_id
    device_data["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return jsonify(device_data)

@app.route('/devices/<device_id>/status')
def get_device_status(device_id):
    """Get device status only - matches USD filterExpression: $.status"""
    if device_id not in devices:
        return jsonify({"error": "Device not found"}), 404
    
    return jsonify({
        "device_id": device_id,
        "status": devices[device_id]["status"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    })

@app.route('/devices/<device_id>/temperature')
def get_device_temperature(device_id):
    """Get device temperature only."""
    if device_id not in devices:
        return jsonify({"error": "Device not found"}), 404
    
    return jsonify({
        "device_id": device_id,
        "temperature": devices[device_id]["temperature"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    })

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "uptime": time.time(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    })

def main():
    print("Starting Device Status API Test Server...")
    print("Server will be available at: http://localhost:5000")
    print("\nTest URLs:")
    print("  - http://localhost:5000/")
    print("  - http://localhost:5000/devices")
    print("  - http://localhost:5000/devices/aircon3245")
    print("  - http://localhost:5000/devices/aircon3245/status")
    print("\nThis matches the USD REQUEST binding configuration:")
    print("  connectionRef: api_prod")
    print("  endpointTarget: /devices/aircon3245/status")
    print("  filterExpression: $.status")
    print("\nPress Ctrl+C to stop\n")
    
    # Start background thread to update device data
    update_thread = threading.Thread(target=update_device_data, daemon=True)
    update_thread.start()
    
    # Start Flask server
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down API server...")

if __name__ == '__main__':
    main()
