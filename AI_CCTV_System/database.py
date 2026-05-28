# database.py
import sqlite3
from datetime import datetime
import json
import os

class Database:
    def __init__(self, db_name='cctv_database.db'):
        """
        Initialize database connection and create tables if not exists
        """
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Create database connection"""
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.cursor = self.conn.cursor()
            print(f"✅ Database connected: {self.db_name}")
        except Exception as e:
            print(f"❌ Database connection error: {e}")
    
    def create_tables(self):
        """Create all required tables"""
        
        # 1. Detections table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                object_class TEXT NOT NULL,
                confidence REAL NOT NULL,
                bbox_x1 INTEGER,
                bbox_y1 INTEGER,
                bbox_x2 INTEGER,
                bbox_y2 INTEGER,
                screenshot_path TEXT,
                alert_sent BOOLEAN DEFAULT 0,
                severity_level TEXT DEFAULT 'medium'
            )
        ''')
        
        # 2. Settings table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. Alerts table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                alert_type TEXT NOT NULL,
                message TEXT,
                object_class TEXT,
                detection_id INTEGER,
                is_read BOOLEAN DEFAULT 0,
                FOREIGN KEY (detection_id) REFERENCES detections(id)
            )
        ''')
        
        # 4. Statistics table for daily counts
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_detections INTEGER DEFAULT 0,
                unique_objects TEXT,
                alert_count INTEGER DEFAULT 0
            )
        ''')
        
        # 5. Recordings table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                file_path TEXT,
                duration INTEGER,
                file_size INTEGER
            )
        ''')
        
        self.conn.commit()
        print("✅ All tables created successfully")
        
        # Insert default settings
        self.insert_default_settings()
    
    def insert_default_settings(self):
        """Insert default system settings"""
        default_settings = [
            ('alert_enabled', 'true'),
            ('alert_sound', 'true'),
            ('alert_classes', json.dumps(['person', 'car', 'truck'])),
            ('confidence_threshold', '0.5'),
            ('save_screenshots', 'true'),
            ('recording_enabled', 'false'),
            ('notification_email', ''),
            ('detection_cooldown', '5')  # seconds
        ]
        
        for key, value in default_settings:
            self.cursor.execute('''
                INSERT OR IGNORE INTO settings (setting_key, setting_value)
                VALUES (?, ?)
            ''', (key, value))
        
        self.conn.commit()
    
    def add_detection(self, object_class, confidence, bbox=None, screenshot_path=None):
        """
        Add a new detection record
        Returns: detection_id
        """
        try:
            if bbox:
                x1, y1, x2, y2 = bbox
            else:
                x1, y1, x2, y2 = None, None, None, None
            
            # Determine severity based on object class
            severity = 'high' if object_class in ['person', 'car', 'truck'] else 'medium'
            
            self.cursor.execute('''
                INSERT INTO detections 
                (object_class, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, 
                 screenshot_path, severity_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (object_class, confidence, x1, y1, x2, y2, screenshot_path, severity))
            
            detection_id = self.cursor.lastrowid
            self.conn.commit()
            
            # Update daily statistics
            self.update_daily_stats(object_class)
            
            # Create alert if needed
            if severity == 'high':
                self.add_alert('object_detected', f'{object_class} detected!', 
                              object_class, detection_id)
            
            return detection_id
            
        except Exception as e:
            print(f"Error adding detection: {e}")
            return None
    
    def add_alert(self, alert_type, message, object_class=None, detection_id=None):
        """Add an alert record"""
        try:
            self.cursor.execute('''
                INSERT INTO alerts (alert_type, message, object_class, detection_id)
                VALUES (?, ?, ?, ?)
            ''', (alert_type, message, object_class, detection_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"Error adding alert: {e}")
            return None
    
    def update_daily_stats(self, object_class):
        """Update daily detection statistics"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if record exists for today
        self.cursor.execute('SELECT * FROM daily_stats WHERE date = ?', (today,))
        record = self.cursor.fetchone()
        
        if record:
            # Update existing record
            current_objects = json.loads(record[2]) if record[2] else []
            if object_class not in current_objects:
                current_objects.append(object_class)
            
            self.cursor.execute('''
                UPDATE daily_stats 
                SET total_detections = total_detections + 1,
                    unique_objects = ?
                WHERE date = ?
            ''', (json.dumps(current_objects), today))
        else:
            # Create new record
            self.cursor.execute('''
                INSERT INTO daily_stats (date, total_detections, unique_objects)
                VALUES (?, 1, ?)
            ''', (today, json.dumps([object_class])))
        
        self.conn.commit()
    
    def get_today_count(self):
        """Get total detections for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.cursor.execute('''
            SELECT total_detections FROM daily_stats WHERE date = ?
        ''', (today,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def get_all_detections(self, limit=100):
        """Get recent detections"""
        self.cursor.execute('''
            SELECT id, timestamp, object_class, confidence, severity_level 
            FROM detections 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        detections = []
        for row in self.cursor.fetchall():
            detections.append({
                'id': row[0],
                'timestamp': row[1],
                'object': row[2],
                'confidence': row[3],
                'severity': row[4]
            })
        return detections
    
    def get_unread_alerts(self):
        """Get unread alerts"""
        self.cursor.execute('''
            SELECT id, timestamp, alert_type, message, object_class 
            FROM alerts 
            WHERE is_read = 0 
            ORDER BY timestamp DESC
        ''')
        
        alerts = []
        for row in self.cursor.fetchall():
            alerts.append({
                'id': row[0],
                'timestamp': row[1],
                'type': row[2],
                'message': row[3],
                'object': row[4]
            })
        return alerts
    
    def mark_alert_read(self, alert_id):
        """Mark alert as read"""
        self.cursor.execute('UPDATE alerts SET is_read = 1 WHERE id = ?', (alert_id,))
        self.conn.commit()
    
    def get_setting(self, key):
        """Get a setting value"""
        self.cursor.execute('SELECT setting_value FROM settings WHERE setting_key = ?', (key,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def update_setting(self, key, value):
        """Update a setting"""
        self.cursor.execute('''
            UPDATE settings 
            SET setting_value = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE setting_key = ?
        ''', (value, key))
        self.conn.commit()
    
    def update_settings(self, key, value):
        """Alias for update_setting"""
        self.update_setting(key, value)
    
    def get_stats_summary(self):
        """Get overall statistics summary"""
        # Total detections all time
        self.cursor.execute('SELECT COUNT(*) FROM detections')
        total = self.cursor.fetchone()[0]
        
        # Detections by class
        self.cursor.execute('''
            SELECT object_class, COUNT(*) as count 
            FROM detections 
            GROUP BY object_class 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        top_classes = [{'class': row[0], 'count': row[1]} for row in self.cursor.fetchall()]
        
        # Today's count
        today_count = self.get_today_count()
        
        # Unread alerts
        unread_alerts = len(self.get_unread_alerts())
        
        return {
            'total_detections': total,
            'today_detections': today_count,
            'top_classes': top_classes,
            'unread_alerts': unread_alerts
        }
    
    def clear_old_detections(self, days=30):
        """Delete detections older than specified days"""
        import datetime
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        
        self.cursor.execute('DELETE FROM detections WHERE date(timestamp) < ?', (cutoff_date,))
        deleted = self.cursor.rowcount
        self.conn.commit()
        return deleted
    
    def add_recording(self, file_path, duration, file_size):
        """Add recording record"""
        try:
            self.cursor.execute('''
                INSERT INTO recordings (start_time, file_path, duration, file_size)
                VALUES (CURRENT_TIMESTAMP, ?, ?, ?)
            ''', (file_path, duration, file_size))
            recording_id = self.cursor.lastrowid
            self.conn.commit()
            return recording_id
        except Exception as e:
            print(f"Error adding recording: {e}")
            return None
    
    def update_recording_end(self, recording_id, end_time=None):
        """Update recording end time"""
        try:
            if end_time is None:
                end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.cursor.execute('''
                UPDATE recordings 
                SET end_time = ? 
                WHERE id = ?
            ''', (end_time, recording_id))
            self.conn.commit()
        except Exception as e:
            print(f"Error updating recording: {e}")
    
    def get_recordings(self, limit=50):
        """Get recent recordings"""
        self.cursor.execute('''
            SELECT id, start_time, end_time, file_path, duration 
            FROM recordings 
            ORDER BY start_time DESC 
            LIMIT ?
        ''', (limit,))
        
        recordings = []
        for row in self.cursor.fetchall():
            recordings.append({
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'file_path': row[3],
                'duration': row[4]
            })
        return recordings
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")
    
    def __del__(self):
        """Destructor - close connection"""
        self.close()


# Quick test function
def test_database():
    """Test database functionality"""
    print("Testing Database...")
    db = Database('test.db')
    
    # Add a test detection
    detection_id = db.add_detection('person', 0.95, [100, 100, 200, 200])
    print(f"Added detection with ID: {detection_id}")
    
    # Get today's count
    today_count = db.get_today_count()
    print(f"Today's detections: {today_count}")
    
    # Get all detections
    detections = db.get_all_detections()
    print(f"Recent detections: {detections}")
    
    # Get stats summary
    stats = db.get_stats_summary()
    print(f"Statistics: {stats}")
    
    # Get unread alerts
    alerts = db.get_unread_alerts()
    print(f"Unread alerts: {alerts}")
    
    # Clean up
    db.close()
    import os
    os.remove('test.db')
    print("Database test passed! ✅")


if __name__ == "__main__":
    test_database()