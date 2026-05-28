# app_final_working.py - Complete Recording & Playback System
from flask import Flask, Response, render_template_string, jsonify, request, send_file
import cv2
from ultralytics import YOLO
import os
import torch
import ultralytics.nn.tasks
from datetime import datetime
import json
from collections import defaultdict
import time
import numpy as np
from threading import Lock
import glob

app = Flask(__name__)

# Thread safety
detection_lock = Lock()

# Store detection data
detections_today = 0
active_detections = 0
detection_history = []
alert_history = []
object_counts = defaultdict(int)
detection_timeline = []
start_time = time.time()
total_frames = 0
fps = 0
last_fps_time = time.time()

# Recording variables
is_recording = False
video_writer = None
current_recording_path = None
recording_start_time = None

# Initialize directories
RECORDINGS_DIR = "recordings"
SCREENSHOTS_DIR = "static/screenshots"
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

print("="*50)
print("🚀 AI CCTV SYSTEM STARTING...")
print("="*50)

# Fix for PyTorch 2.6+ compatibility
try:
    torch.serialization.add_safe_globals([ultralytics.nn.tasks.DetectionModel])
    print("✅ Applied PyTorch compatibility fix")
except:
    pass

# Load YOLO model
model_path = 'yolov8n.pt'
if os.path.exists(model_path):
    print(f"✅ Model found at {model_path}")
    model = YOLO(model_path)
else:
    print("📥 Downloading YOLO model...")
    model = YOLO('yolov8n.pt')
print("✅ Model loaded!")

# Initialize camera
print("📷 Opening camera...")
camera = cv2.VideoCapture(0)
if not camera.isOpened():
    camera = cv2.VideoCapture(1)
if not camera.isOpened():
    print("⚠️ Camera not found - Test mode")
    camera = None
else:
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    print("✅ Camera ready!")

# Dashboard HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Smart CCTV | Professional Surveillance</title>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }
        
        body {
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
        }
        
        /* Navbar */
        .navbar {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .navbar-brand {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: bold;
        }
        
        /* Stats Cards */
        .stats-card {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .stats-card:hover {
            transform: translateY(-5px);
        }
        
        .stats-number {
            font-size: 2rem;
            font-weight: bold;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        /* Video Container */
        .video-container {
            background: black;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        
        .live-video {
            width: 100%;
            height: auto;
        }
        
        /* Recording Button */
        .btn-record {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            border: none;
            padding: 12px 30px;
            border-radius: 30px;
            color: white;
            font-weight: bold;
            transition: 0.3s;
        }
        
        .btn-record:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(239,68,68,0.4);
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #6b7280, #4b5563);
            border: none;
            padding: 12px 30px;
            border-radius: 30px;
            color: white;
            font-weight: bold;
        }
        
        .btn-custom {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border: none;
            padding: 12px 25px;
            border-radius: 30px;
            color: white;
            font-weight: bold;
            margin: 5px;
            transition: 0.3s;
        }
        
        .btn-custom:hover {
            transform: scale(1.05);
        }
        
        /* Recording Indicator */
        .recording-indicator {
            position: fixed;
            top: 80px;
            right: 20px;
            background: rgba(239,68,68,0.9);
            padding: 8px 16px;
            border-radius: 30px;
            color: white;
            font-weight: bold;
            z-index: 1000;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .recording-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: white;
            border-radius: 50%;
            margin-right: 8px;
            animation: blink 1s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* Recordings Grid */
        .recordings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .recording-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            transition: 0.3s;
            cursor: pointer;
        }
        
        .recording-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        }
        
        .recording-preview {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            height: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        
        .recording-preview i {
            font-size: 60px;
            color: rgba(255,255,255,0.4);
        }
        
        .delete-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(239,68,68,0.9);
            border: none;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: 0.3s;
            z-index: 10;
        }
        
        .delete-btn:hover {
            background: #dc2626;
            transform: scale(1.1);
        }
        
        .recording-info {
            padding: 15px;
        }
        
        .recording-name {
            font-weight: bold;
            color: var(--primary);
        }
        
        .recording-size {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }
        
        /* Modal for video playback */
        .video-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 2000;
            align-items: center;
            justify-content: center;
        }
        
        .video-modal.active {
            display: flex;
        }
        
        .video-modal-content {
            max-width: 90%;
            position: relative;
        }
        
        .video-modal video {
            width: 100%;
            max-height: 80vh;
            border-radius: 15px;
        }
        
        .close-modal {
            position: absolute;
            top: -40px;
            right: 0;
            color: white;
            font-size: 35px;
            cursor: pointer;
        }
        
        /* Alerts */
        .alert-item {
            margin-bottom: 10px;
            padding: 12px;
            border-radius: 10px;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .alert-danger {
            background: linear-gradient(135deg, #fee2e2, #fee);
            border-left: 4px solid #ef4444;
        }
        
        .alert-warning {
            background: linear-gradient(135deg, #fed7aa, #fea);
            border-left: 4px solid #f59e0b;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .stats-number { font-size: 1.5rem; }
            .recordings-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <!-- Navbar -->
    <nav class="navbar navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-shield-alt"></i> AI Smart CCTV Surveillance
            </a>
            <div class="d-flex">
                <button class="btn btn-outline-light me-2" onclick="showSection('live')">
                    <i class="fas fa-video"></i> Live
                </button>
                <button class="btn btn-outline-light" onclick="showSection('recordings')">
                    <i class="fas fa-history"></i> Recordings
                </button>
            </div>
        </div>
    </nav>
    
    <!-- Recording Indicator -->
    <div id="recordingIndicator" class="recording-indicator" style="display: none;">
        <span class="recording-dot"></span> RECORDING
    </div>
    
    <div class="container-fluid py-4">
        <!-- Stats Row -->
        <div class="row mb-4">
            <div class="col-md-3 mb-3">
                <div class="stats-card">
                    <i class="fas fa-eye" style="font-size: 30px; color: var(--primary);"></i>
                    <div class="stats-number" id="activeDetections">0</div>
                    <div class="text-muted">Active Detections</div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="stats-card">
                    <i class="fas fa-chart-line" style="font-size: 30px; color: var(--success);"></i>
                    <div class="stats-number" id="totalToday">0</div>
                    <div class="text-muted">Today's Events</div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="stats-card">
                    <i class="fas fa-video" style="font-size: 30px; color: var(--warning);"></i>
                    <div class="stats-number" id="totalRecordings">0</div>
                    <div class="text-muted">Total Recordings</div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="stats-card">
                    <i class="fas fa-tachometer-alt" style="font-size: 30px; color: var(--secondary);"></i>
                    <div class="stats-number" id="fpsValue">0</div>
                    <div class="text-muted">FPS</div>
                </div>
            </div>
        </div>
        
        <!-- Live Section -->
        <div id="liveSection">
            <div class="row">
                <div class="col-lg-8 mb-3">
                    <div class="video-container">
                        <img src="{{ url_for('video_feed') }}" class="live-video" id="liveFeed" alt="Live Feed">
                    </div>
                    <div class="mt-3 text-center">
                        <button id="recordBtn" class="btn-record" onclick="toggleRecording()">
                            <i class="fas fa-circle"></i> Start Recording
                        </button>
                        <button class="btn-custom" onclick="captureScreenshot()">
                            <i class="fas fa-camera"></i> Screenshot
                        </button>
                        <button class="btn-custom" onclick="refreshFeed()">
                            <i class="fas fa-sync-alt"></i> Refresh
                        </button>
                    </div>
                </div>
                <div class="col-lg-4 mb-3">
                    <div class="stats-card" style="height: 500px; overflow-y: auto;">
                        <h5><i class="fas fa-bell"></i> Live Alerts</h5>
                        <hr>
                        <div id="alertsList">
                            <div class="alert alert-info">Waiting for detections...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Recordings Section -->
        <div id="recordingsSection" style="display: none;">
            <div class="stats-card">
                <h5><i class="fas fa-history"></i> Saved Recordings</h5>
                <hr>
                <div id="recordingsList" class="recordings-grid">
                    <!-- Recordings will be loaded here -->
                </div>
            </div>
        </div>
    </div>
    
    <!-- Video Modal -->
    <div class="video-modal" id="videoModal">
        <div class="video-modal-content">
            <span class="close-modal" onclick="closeModal()">&times;</span>
            <video id="modalVideo" controls>
                <source id="videoSource" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
    </div>
    
    <script>
        // Show sections
        function showSection(section) {
            if (section === 'live') {
                document.getElementById('liveSection').style.display = 'block';
                document.getElementById('recordingsSection').style.display = 'none';
            } else {
                document.getElementById('liveSection').style.display = 'none';
                document.getElementById('recordingsSection').style.display = 'block';
                loadRecordings();
            }
        }
        
        // Toggle recording
        async function toggleRecording() {
            const btn = document.getElementById('recordBtn');
            const indicator = document.getElementById('recordingIndicator');
            
            const response = await fetch('/api/toggle_recording', { method: 'POST' });
            const data = await response.json();
            
            if (data.recording) {
                btn.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
                btn.className = 'btn-stop';
                indicator.style.display = 'block';
                showToast('🔴 Recording started!', 'success');
            } else {
                btn.innerHTML = '<i class="fas fa-circle"></i> Start Recording';
                btn.className = 'btn-record';
                indicator.style.display = 'none';
                showToast('✅ Recording saved!', 'success');
                loadRecordings();
                loadTotalRecordings();
            }
        }
        
        // Load recordings list
        async function loadRecordings() {
            const response = await fetch('/api/list_recordings');
            const data = await response.json();
            
            const container = document.getElementById('recordingsList');
            if (data.recordings.length === 0) {
                container.innerHTML = '<div class="alert alert-info">No recordings found. Click Start Recording to create one!</div>';
                return;
            }
            
            container.innerHTML = data.recordings.map(rec => `
                <div class="recording-card" onclick="playRecording('${rec.path}')">
                    <div class="recording-preview">
                        <button class="delete-btn" onclick="event.stopPropagation(); deleteRecording('${rec.path}')">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                        <i class="fas fa-video"></i>
                    </div>
                    <div class="recording-info">
                        <div class="recording-name"><i class="far fa-clock"></i> ${rec.name}</div>
                        <div class="recording-size"><i class="fas fa-hdd"></i> ${rec.size} MB</div>
                        <div class="recording-size"><i class="far fa-calendar"></i> ${rec.date} ${rec.time}</div>
                    </div>
                </div>
            `).join('');
        }
        
        // Play recording
        function playRecording(path) {
            const modal = document.getElementById('videoModal');
            const video = document.getElementById('modalVideo');
            video.src = path;
            modal.classList.add('active');
            video.play();
        }
        
        // Delete recording
        async function deleteRecording(path) {
            if (confirm('Are you sure you want to delete this recording?')) {
                const response = await fetch('/api/delete_recording', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });
                const data = await response.json();
                if (data.success) {
                    showToast('Recording deleted!', 'success');
                    loadRecordings();
                    loadTotalRecordings();
                } else {
                    showToast('Delete failed!', 'error');
                }
            }
        }
        
        // Close modal
        function closeModal() {
            const modal = document.getElementById('videoModal');
            const video = document.getElementById('modalVideo');
            video.pause();
            video.src = '';
            modal.classList.remove('active');
        }
        
        // Capture screenshot
        async function captureScreenshot() {
            const response = await fetch('/api/capture_screenshot', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showToast('📸 Screenshot saved!', 'success');
            }
        }
        
        // Refresh feed
        function refreshFeed() {
            const img = document.getElementById('liveFeed');
            img.src = img.src.split('?')[0] + '?' + new Date().getTime();
            showToast('Feed refreshed!', 'info');
        }
        
        // Show toast notification
        function showToast(message, type) {
            const toast = document.createElement('div');
            toast.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} position-fixed bottom-0 end-0 m-3`;
            toast.style.zIndex = '9999';
            toast.style.animation = 'slideIn 0.3s ease';
            toast.innerHTML = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        // Update stats
        async function updateStats() {
            const response = await fetch('/api/stats');
            const data = await response.json();
            document.getElementById('activeDetections').innerText = data.active_detections || 0;
            document.getElementById('totalToday').innerText = data.total_detections_today || 0;
            document.getElementById('fpsValue').innerText = data.fps || 0;
        }
        
        // Update alerts
        async function updateAlerts() {
            const response = await fetch('/api/detections');
            const data = await response.json();
            const container = document.getElementById('alertsList');
            if (data.alerts && data.alerts.length > 0) {
                container.innerHTML = data.alerts.slice(0, 10).map(alert => `
                    <div class="alert-item alert-${alert.type}">
                        <strong><i class="fas fa-${alert.icon}"></i> ${alert.object.toUpperCase()}</strong>
                        <br><small>Confidence: ${(alert.confidence * 100).toFixed(1)}%</small>
                        <br><small>Time: ${alert.time}</small>
                    </div>
                `).join('');
            }
        }
        
        // Load total recordings count
        async function loadTotalRecordings() {
            const response = await fetch('/api/total_recordings');
            const data = await response.json();
            document.getElementById('totalRecordings').innerText = data.total || 0;
        }
        
        // Auto refresh every 2 seconds
        setInterval(() => {
            updateStats();
            updateAlerts();
        }, 2000);
        
        // Initial load
        updateStats();
        updateAlerts();
        loadTotalRecordings();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/video_feed')
def video_feed():
    def generate():
        global detections_today, active_detections, alert_history, object_counts, detection_timeline, total_frames, fps, last_fps_time, is_recording, video_writer, current_recording_path
        
        frame_count = 0
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        while True:
            if camera is None:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "Camera Not Found", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                success, frame = camera.read()
                if not success:
                    break
                
                # FPS calculation
                total_frames += 1
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    fps = total_frames
                    total_frames = 0
                    last_fps_time = current_time
                
                # Run detection every 2nd frame
                if frame_count % 2 == 0:
                    results = model(frame, verbose=False)
                    frame = results[0].plot()
                    
                    # Update detection stats
                    current_detections = []
                    if results[0].boxes is not None:
                        for box in results[0].boxes:
                            cls = int(box.cls[0])
                            conf = float(box.conf[0])
                            name = model.names[cls]
                            current_detections.append({'class': name, 'confidence': conf})
                            
                            with detection_lock:
                                object_counts[name] += 1
                                detections_today += 1
                                
                                if conf > 0.6:
                                    alert_history.insert(0, {
                                        'time': datetime.now().strftime('%H:%M:%S'),
                                        'object': name,
                                        'confidence': conf,
                                        'type': 'danger' if name in ['person'] else 'warning',
                                        'icon': 'user' if name == 'person' else 'circle'
                                    })
                                    if len(alert_history) > 50:
                                        alert_history.pop()
                    
                    active_detections = len(current_detections)
                    detection_timeline.append({'time': datetime.now().strftime('%H:%M:%S'), 'count': active_detections})
                    if len(detection_timeline) > 30:
                        detection_timeline.pop(0)
                
                # Handle recording - SAVE VIDEO
                if is_recording:
                    if video_writer is None:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        current_recording_path = os.path.join(RECORDINGS_DIR, f"recording_{timestamp}.mp4")
                        video_writer = cv2.VideoWriter(current_recording_path, fourcc, 20.0, (frame.shape[1], frame.shape[0]))
                        print(f"🎥 Recording started: {current_recording_path}")
                    if video_writer is not None:
                        video_writer.write(frame)
                else:
                    if video_writer is not None:
                        video_writer.release()
                        video_writer = None
                        print(f"💾 Recording saved: {current_recording_path}")
                        current_recording_path = None
                
                frame_count += 1
            
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stats')
def get_stats():
    global active_detections, detections_today, start_time, fps
    return jsonify({
        'active_detections': active_detections,
        'total_detections_today': detections_today,
        'uptime_seconds': int(time.time() - start_time),
        'fps': fps
    })

@app.route('/api/detections')
def get_detections():
    global detection_timeline, object_counts, alert_history
    with detection_lock:
        top_objects = sorted(object_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return jsonify({
            'alerts': alert_history[:15],
            'chart_labels': [d['time'] for d in detection_timeline[-20:]],
            'chart_data': [d['count'] for d in detection_timeline[-20:]],
            'object_labels': [obj[0] for obj in top_objects],
            'object_counts': [obj[1] for obj in top_objects]
        })

@app.route('/api/list_recordings')
def list_recordings():
    recordings = []
    if os.path.exists(RECORDINGS_DIR):
        for f in sorted(os.listdir(RECORDINGS_DIR), reverse=True):
            if f.endswith('.mp4'):
                file_path = os.path.join(RECORDINGS_DIR, f)
                file_size = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                recordings.append({
                    'name': f,
                    'path': f'/recordings/{f}',
                    'size': file_size,
                    'date': file_time.strftime('%Y-%m-%d'),
                    'time': file_time.strftime('%H:%M:%S')
                })
    return jsonify({'recordings': recordings})

@app.route('/recordings/<filename>')
def serve_recording(filename):
    return send_file(os.path.join(RECORDINGS_DIR, filename))

@app.route('/api/total_recordings')
def total_recordings():
    count = 0
    if os.path.exists(RECORDINGS_DIR):
        count = len([f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.mp4')])
    return jsonify({'total': count})

@app.route('/api/toggle_recording', methods=['POST'])
def toggle_recording():
    global is_recording
    is_recording = not is_recording
    return jsonify({'recording': is_recording})

@app.route('/api/capture_screenshot', methods=['POST'])
def capture_screenshot():
    global camera
    if camera is not None:
        success, frame = camera.read()
        if success:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SCREENSHOTS_DIR, f"screenshot_{timestamp}.jpg")
            cv2.imwrite(path, frame)
            return jsonify({'success': True, 'path': path})
    return jsonify({'success': False})

@app.route('/api/delete_recording', methods=['POST'])
def delete_recording():
    data = request.get_json()
    path = data.get('path', '')
    filename = os.path.basename(path)
    full_path = os.path.join(RECORDINGS_DIR, filename)
    if os.path.exists(full_path):
        os.remove(full_path)
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/clear_alerts', methods=['POST'])
def clear_alerts():
    global alert_history
    alert_history = []
    return jsonify({'success': True})

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎯 Dashboard: http://localhost:5000")
    print("📹 Recording: Click 'Start Recording' button")
    print("💾 Videos save to: recordings/ folder")
    print("▶️ Playback: Click any recording to play")
    print("🗑️ Delete: Click trash icon on any recording")
    print("="*50 + "\n")
    app.run(debug=False, port=5000, use_reloader=False, threaded=True)