import os
import sqlite3
import datetime
import threading
import webbrowser
import time
import random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

from jinja2 import ChoiceLoader, FileSystemLoader

try:
    import webview
    from waitress import serve
except ImportError:
    pass

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def run_flask():
    print("Attempting to start server on port 5003...")
    
    # Run the server in a separate thread
    def start_server():
        try:
            serve(app, host="127.0.0.1", port=5003)
        except NameError:
            app.run(port=5003, debug=False, use_reloader=False)
            
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Wait for server to initialize
    time.sleep(1)
    
    try:
        import webview
        print("Launching desktop window...")
        webview.create_window('Tea Transfers - Branch 1', 'http://127.0.0.1:5003', width=1200, height=800)
        webview.start()
    except ImportError:
        print("pywebview not found. Opening in default browser instead...")
        webbrowser.open("http://127.0.0.1:5003")
        # Keep the main thread alive if we don't have webview
        while True:
            time.sleep(10)

def get_db_path():
    # 1. Target local path (where the EXE/script is)
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    local_db = os.path.join(base_dir, 'KOKKALATTY_TRANSFERS.db')
    
    # 2. Documents path (Standard location for user data)
    docs_path = os.path.join(os.path.expanduser("~"), "Documents")
    if not os.path.exists(docs_path):
        os.makedirs(docs_path, exist_ok=True)
        
    documents_db = os.path.join(docs_path, 'KOKKALATTY_TRANSFERS.db')
    
    # Check priority: Local first, then Documents
    if os.path.exists(local_db):
        return local_db
    elif os.path.exists(documents_db):
        return documents_db
    else:
        # Default to Documents for new installs
        return documents_db

app = Flask(__name__,
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))

# Configure multi-folder template loading
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(resource_path('templates')),
    FileSystemLoader(resource_path('branch1/templates')),
    FileSystemLoader(resource_path('branch2/templates')),
    FileSystemLoader(resource_path('.')) # For login.html at root
])

app.secret_key = 'factory_transfer_secret_key_789'

# Database Setup
DB_FILE = get_db_path()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Parent Invoices Table
    conn.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT,
        date TEXT,
        time TEXT,
        user TEXT,
        total_items INTEGER,
        total_qty REAL,
        total_packages INTEGER,
        received_packets INTEGER DEFAULT 0,
        status TEXT DEFAULT 'SENT',
        manual_sno TEXT
    )''')
    
    # Child Transfer Items Table
    conn.execute('''CREATE TABLE IF NOT EXISTS transfer_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        batch_no TEXT,
        grade TEXT,
        uom TEXT DEFAULT 'KG',
        num_packages INTEGER,
        sn_from INTEGER,
        sn_to INTEGER,
        nett_wt REAL,
        total_qty REAL,
        description TEXT,
        received_packages INTEGER DEFAULT 0,
        received_packets INTEGER DEFAULT 0,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id)
    )''')
    
    # Run migrations for existing DB
    try:
        conn.execute('ALTER TABLE invoices ADD COLUMN status TEXT DEFAULT "SENT"')
    except: pass
    try:
        conn.execute('ALTER TABLE invoices ADD COLUMN received_packets INTEGER DEFAULT 0')
    except: pass
    try:
        conn.execute('ALTER TABLE invoices ADD COLUMN received_date TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE invoices ADD COLUMN total_received_bags INTEGER DEFAULT 0')
    except: pass
    try:
        conn.execute('ALTER TABLE transfer_items ADD COLUMN description TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE transfer_items ADD COLUMN received_packages INTEGER DEFAULT 0')
    except: pass
    try:
        conn.execute('ALTER TABLE transfer_items ADD COLUMN received_packets INTEGER DEFAULT 0')
    except: pass
    try:
        conn.execute('ALTER TABLE transfer_items ADD COLUMN packets_sent INTEGER DEFAULT 0')
    except: pass
    try:
        conn.execute('ALTER TABLE transfer_items ADD COLUMN hsn_code TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE invoices ADD COLUMN manual_sno TEXT')
    except: pass
    
    # Branch1 Specific Tables
    conn.execute('''CREATE TABLE IF NOT EXISTS branch1_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sl_no INTEGER,
        grade TEXT,
        batch_invoice_no TEXT,
        no_of_packages INTEGER,
        serial_from INTEGER,
        serial_to INTEGER,
        net_weight_kgs REAL,
        total_qty_kg REAL,
        entry_date TEXT,
        entry_time TEXT,
        group_id TEXT
    )''')
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN group_id TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN destination_name TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN destination_address TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN destination_gstin TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN vehicle_no TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN hsn_code TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN gross_weight REAL')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN bag_weight REAL')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN unit_weight REAL')
    except: pass
    
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN driver_name TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN driver_no TEXT')
    except: pass
    
    conn.execute('''CREATE TABLE IF NOT EXISTS branch1_drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        phone TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS branch1_vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_no TEXT UNIQUE
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS branch1_destinations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        address TEXT,
        gstin TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS branch1_production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        batch_no TEXT,
        grade TEXT,
        qty_produced REAL,
        no_of_packages INTEGER,
        uom TEXT DEFAULT 'KG',
        notes TEXT
    )''')
    
    # Migrations for branch1_production
    try:
        conn.execute('ALTER TABLE branch1_production ADD COLUMN batch_no TEXT')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_production ADD COLUMN no_of_packages INTEGER')
    except: pass
    try:
        conn.execute('ALTER TABLE branch1_production ADD COLUMN uom TEXT DEFAULT "KG"')
    except: pass
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')
    
    conn.commit()
    conn.close()

# Initialize DB on start
init_db()

def get_user(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

# Seed users if none exist
def seed_users():
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if count == 0:
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('branch1', '123'))
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('branch2', '123'))
        conn.commit()
    conn.close()

seed_users()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = get_user(username)
    if user and user['password'] == password:
        session['username'] = username
        return redirect(url_for('dashboard'))
    
    return redirect(url_for('index', error='invalid'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dispatch')
def dispatch():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    today_str = datetime.datetime.now().strftime("%d/%m/%Y")
    
    # Get itemized transactions for dispatch history log
    transactions = conn.execute('''
        SELECT i.id, i.date, i.status, i.invoice_no, i.time, i.manual_sno,
               t.grade, t.num_packages, t.received_packets, t.nett_wt, t.total_qty
        FROM invoices i
        JOIN transfer_items t ON i.id = t.invoice_id
        WHERE i.invoice_no LIKE 'DIS-%' OR i.invoice_no LIKE 'TRF-%'
        ORDER BY i.id DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('dispatch.html', transactions=transactions, today=today_str)

@app.route('/received')
def received():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    # Get invoices with aggregated item summaries for the history log
    invoices_data = conn.execute('''
        SELECT i.id, i.date, i.status, i.invoice_no, i.manual_sno,
               GROUP_CONCAT(t.grade || ' (' || COALESCE(t.received_packages, t.num_packages) || ' Bags)', ', ') as items_summary,
               SUM(COALESCE(t.received_packages, t.num_packages) * t.nett_wt) as total_weight
        FROM invoices i
        JOIN transfer_items t ON i.id = t.invoice_id
        WHERE i.invoice_no LIKE 'ARR-%' OR i.invoice_no LIKE 'TRF-%'
        GROUP BY i.id
        ORDER BY i.id DESC
    ''').fetchall()
    
    # Regular invoices for the verification modal
    pending_invoices = conn.execute('SELECT * FROM invoices WHERE status != "RECEIVED" ORDER BY id DESC').fetchall()
    
    # Grade-wise summary for Received Stock
    grade_summary = conn.execute('''
        SELECT 
            t.grade, 
            SUM(t.received_packages) as total_bags, 
            SUM(t.received_packages * t.nett_wt) as total_weight
        FROM transfer_items t
        INNER JOIN invoices i ON t.invoice_id = i.id
        WHERE i.status = 'RECEIVED'
        GROUP BY t.grade
    ''').fetchall()
    
    conn.close()
    
    return render_template('received.html', invoices=invoices_data, pending_invoices=pending_invoices, grade_summary=grade_summary)

@app.route('/summary')
def summary():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    # Per-entry summary (not grouped — each invoice entry is its own row)
    overall_summary = conn.execute('''
        SELECT 
            i.manual_sno as sno,
            i.invoice_no,
            i.date,
            t.grade,
            t.num_packages      as total_bags_sent,
            t.received_packages as total_bags_received,
            t.received_packets  as total_packets_made,
            (t.received_packages * t.nett_wt) as stock_weight
        FROM transfer_items t
        INNER JOIN invoices i ON t.invoice_id = i.id
        ORDER BY i.id ASC, t.id ASC
    ''').fetchall()
    
    conn.close()
    return render_template('summary.html', summary_data=overall_summary)

@app.route('/dashboard')
def dashboard():
    # Legacy redirect or decide which one is the default dashboard
    if 'username' not in session:
        return redirect(url_for('index'))
    if session['username'] == 'branch1':
        return redirect(url_for('branch1_transfer'))
    else:
        return redirect(url_for('received'))

# --- BRANCH 1 HANDLERS ---

@app.route('/branch1/transfer')
def branch1_transfer():
    if 'username' not in session or session['username'] != 'branch1':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    # Group history by group_id to show invoices instead of individual rows
    history = conn.execute('''
        SELECT 
            group_id, 
            entry_date, 
            entry_time, 
            COUNT(*) as item_count, 
            SUM(no_of_packages) as total_packages, 
            SUM(total_qty_kg) as grand_total_qty,
            GROUP_CONCAT(grade, ", ") as grades,
            MIN(batch_invoice_no) as ref_no,
            MIN(destination_name) as dest_name,
            MIN(vehicle_no) as vehicle_no
        FROM branch1_transfers 
        GROUP BY group_id 
        ORDER BY id DESC LIMIT 50
    ''').fetchall()
    conn.close()
    
    return render_template('transfer.html', history=history)

@app.route('/branch1/production')
def branch1_production():
    if 'username' not in session or session['username'] != 'branch1':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    history = conn.execute('SELECT * FROM branch1_production ORDER BY id DESC LIMIT 50').fetchall()
    conn.close()
    
    return render_template('production.html', history=history)

@app.route('/api/branch1/production/save', methods=['POST'])
def save_branch1_production():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    data = request.json
    item_id = data.get('id')
    try:
        conn = get_db_connection()
        if item_id:
            conn.execute('''UPDATE branch1_production 
                           SET batch_no = ?, grade = ?, qty_produced = ?, no_of_packages = ?, uom = ?, notes = ?
                           WHERE id = ?''',
                        (data['batch_no'], data['grade'], data['qty'], 
                         data['packages'], data['uom'], data.get('notes', ''), item_id))
        else:
            conn.execute('''INSERT INTO branch1_production 
                           (date, batch_no, grade, qty_produced, no_of_packages, uom, notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (data['date'], data['batch_no'], data['grade'], data['qty'], 
                         data['packages'], data['uom'], data.get('notes', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/branch1/production/delete/<int:item_id>', methods=['POST'])
def delete_branch1_production(item_id):
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM branch1_production WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/branch1/transfer/save', methods=['POST'])
def save_branch1_transfer():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    data = request.json
    items = data.get('items', [])
    existing_group_id = data.get('group_id')
    
    if not items:
        return jsonify({'success': False, 'message': 'No items to save'})
    
    try:
        conn = get_db_connection()
        now = datetime.datetime.now()
        
        if existing_group_id:
            # Update mode: Delete old entries first
            conn.execute('DELETE FROM branch1_transfers WHERE group_id = ?', (existing_group_id,))
            group_id = existing_group_id
            date_str = data.get('date', now.strftime("%d/%m/%Y"))
            time_str = data.get('time', now.strftime("%I:%M %p"))
        else:
            date_str = now.strftime("%d/%m/%Y")
            time_str = now.strftime("%I:%M %p")
            group_id = f"G-{now.strftime('%y%m%d%H%M%S')}-{random.randint(10,99)}"
        
        destination = data.get('destination', {})
        dest_name = destination.get('name', 'SELF')
        dest_addr = destination.get('address', '')
        dest_gstin = destination.get('gstin', '')
        vehicle_no = data.get('vehicle_no', '')

        driver_name = data.get('driver_name', '')
        driver_no = data.get('driver_no', '')

        # Save destination if new or updated
        if dest_name and dest_name != 'SELF':
            conn.execute('''INSERT OR REPLACE INTO branch1_destinations (name, address, gstin) 
                           VALUES (?, ?, ?)''', (dest_name, dest_addr, dest_gstin))
        
        # Save vehicle_no if new
        if vehicle_no:
            conn.execute('INSERT OR IGNORE INTO branch1_vehicles (vehicle_no) VALUES (?)', (vehicle_no,))

        # Save driver if new
        if driver_name:
            conn.execute('''INSERT OR REPLACE INTO branch1_drivers (name, phone) 
                           VALUES (?, ?)''', (driver_name, driver_no))

        for item in items:
            conn.execute('''INSERT INTO branch1_transfers 
                           (sl_no, grade, batch_invoice_no, hsn_code, no_of_packages, serial_from, serial_to, net_weight_kgs, total_qty_kg, entry_date, entry_time, group_id, destination_name, destination_address, destination_gstin, vehicle_no, gross_weight, bag_weight, unit_weight, driver_name, driver_no)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (item['slNo'], item['grade'], item['batch'], item.get('hsn', ''), item['pkgs'], 
                         item['snFrom'], item['snTo'], item['netWt'], item['totalQty'], date_str, time_str, group_id, dest_name, dest_addr, dest_gstin, vehicle_no, item.get('grossWt'), item.get('bagWt'), item.get('unitWt'), driver_name, driver_no))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'group_id': group_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/branch1/transfer/delete/<group_id>', methods=['POST'])
def delete_branch1_transfer_group(group_id):
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM branch1_transfers WHERE group_id = ?', (group_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/branch1/transfer/details/<group_id>')
def get_branch1_transfer_details(group_id):
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify({'success': False}), 403
    
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM branch1_transfers WHERE group_id = ? ORDER BY id ASC', (group_id,)).fetchall()
    conn.close()
    
    return jsonify([dict(item) for item in items])

@app.route('/api/branch1/vehicles')
def get_branch1_vehicles():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify([]), 403
    conn = get_db_connection()
    rows = conn.execute('SELECT vehicle_no FROM branch1_vehicles ORDER BY vehicle_no ASC').fetchall()
    conn.close()
    return jsonify([row['vehicle_no'] for row in rows])

@app.route('/api/branch1/destinations')
def get_branch1_destinations():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify([]), 403
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM branch1_destinations ORDER BY name ASC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/branch1/drivers')
def get_branch1_drivers():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify([]), 403
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM branch1_drivers ORDER BY name ASC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/branch1/grades')
def get_branch1_grades():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify([]), 403
    conn = get_db_connection()
    # Get unique grades from transfers and production
    rows = conn.execute('''
        SELECT DISTINCT grade FROM branch1_transfers WHERE grade IS NOT NULL
        UNION
        SELECT DISTINCT grade FROM branch1_production WHERE grade IS NOT NULL
        ORDER BY grade ASC
    ''').fetchall()
    conn.close()
    return jsonify([row['grade'] for row in rows])


@app.route('/api/branch1/last_serial')
def get_branch1_last_serial():
    if 'username' not in session or session['username'] != 'branch1':
        return jsonify({'last_serial': 0}), 403
    conn = get_db_connection()
    row = conn.execute('SELECT MAX(serial_to) as last_val FROM branch1_transfers').fetchone()
    conn.close()
    last_val = row['last_val'] if row['last_val'] else 0
    return jsonify({'last_serial': last_val})


@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('settings.html')

@app.route('/api/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json
    current_username = data.get('current_username')
    current_password = data.get('current_password')
    new_username = data.get('new_username')
    new_password = data.get('new_password')
    
    if not current_username or not current_password or not new_username or not new_password:
        return jsonify({'success': False, 'message': 'All fields are required'})
    
    user = get_user(session['username'])
    if not user or user['username'] != current_username or user['password'] != current_password:
        return jsonify({'success': False, 'message': 'Current Username or Password incorrect'})
    
    try:
        conn = get_db_connection()
        conn.execute('UPDATE users SET username = ?, password = ? WHERE id = ?', 
                     (new_username, new_password, user['id']))
        conn.commit()
        conn.close()
        
        # Update session with new username
        session['username'] = new_username
        
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'New username already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})




@app.route('/api/invoice/details/<int:invoice_id>')
def get_invoice_details(invoice_id):
    if 'username' not in session:
        return jsonify({'success': False}), 403
    
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM transfer_items WHERE invoice_id = ?', (invoice_id,)).fetchall()
    conn.close()
    
    return jsonify([dict(item) for item in items])

@app.route('/api/invoice/add', methods=['POST'])
def add_invoice():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json
    try:
        invoice_no = data.get('invoice_no')
        items = data.get('items', [])
        
        if not items:
            return jsonify({'success': False, 'message': 'No items added'})
            
        now = datetime.datetime.now()
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M:%S")
        
        total_items = len(items)
        total_qty = sum(float(i['total_qty']) for i in items)
        total_packages = sum(int(i['num_packages']) for i in items)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Auto-generate Ref if not provided
        if not invoice_no:
            now = datetime.datetime.now()
            count_res = conn.execute('SELECT COUNT(*) as count FROM invoices WHERE date = ?', (now.strftime("%d/%m/%Y"),)).fetchone()
            daily_count = (count_res['count'] if count_res else 0) + 1
            invoice_no = f"TRF-{now.strftime('%y%m%d')}-{daily_count:03d}"

        # Insert Parent Invoice
        cur.execute('''INSERT INTO invoices (invoice_no, date, time, user, total_items, total_qty, total_packages, status) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (invoice_no, date_str, time_str, session['username'], total_items, total_qty, total_packages, 'SENT'))
        invoice_id = cur.lastrowid
        
        # Insert Child Items
        for i in items:
            cur.execute('''INSERT INTO transfer_items 
                           (invoice_id, batch_no, grade, hsn_code, uom, num_packages, sn_from, sn_to, nett_wt, total_qty, description, received_packages, received_packets, packets_sent) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (invoice_id, i['batch_no'], i['grade'], i.get('hsn', ''), i['uom'], i['num_packages'], 
                         i['sn_from'], i['sn_to'], i['nett_wt'], i['total_qty'], i.get('description', ''), i.get('num_packages', 0), 0, i.get('packets_sent', 0)))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/invoice/update_receipt', methods=['POST'])
def update_receipt():
    if 'username' not in session:
        return jsonify({'success': False}), 403
    
    data = request.json
    invoice_id = data.get('invoice_id')
    items = data.get('items', [])
    
    conn = get_db_connection()
    total_packets = 0
    total_bags = 0
    now = datetime.datetime.now()
    received_date = now.strftime("%d/%m/%Y")
    
    for item in items:
        conn.execute('UPDATE transfer_items SET received_packages = ?, received_packets = ? WHERE id = ?', 
                     (item['received_bags'], item['received_packets'], item['id']))
        total_packets += item['received_packets']
        total_bags += item['received_bags']
    
    conn.execute('UPDATE invoices SET status = "RECEIVED", received_packets = ?, total_received_bags = ?, received_date = ? WHERE id = ?', 
                 (total_packets, total_bags, received_date, invoice_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/arrival/manual/add', methods=['POST'])
def add_manual_arrival():
    if 'username' not in session:
        return jsonify({'success': False}), 403
    
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Generate automatic Ref for Manual Arrival
        now = datetime.datetime.now()
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M:%S")

        prefix = data.get('prefix', 'ARR')
        manual_sno = data.get('manual_sno')
        
        count_res = conn.execute('SELECT COUNT(*) as count FROM invoices WHERE date = ?', (date_str,)).fetchone()
        daily_count = (count_res['count'] if count_res else 0) + 1
        invoice_no = f"{prefix}-{now.strftime('%y%m%d')}-{daily_count:03d}"

        items = data.get('items', [])
        
        total_items = len(items)
        total_packages = sum(int(i['received_bags']) for i in items)
        total_packets = sum(int(i['received_packets']) for i in items)
        total_qty = sum(float(i.get('total_qty', 0)) for i in items)
        
        # Insert as already RECEIVED
        cur.execute('''INSERT INTO invoices (invoice_no, date, time, user, total_items, total_qty, total_packages, received_packets, total_received_bags, status, received_date, manual_sno) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (invoice_no, date_str, time_str, session['username'], total_items, total_qty, total_packages, total_packets, total_packages, 'RECEIVED', date_str, manual_sno))
        
        invoice_id = cur.lastrowid
        
        for i in items:
            cur.execute('''INSERT INTO transfer_items 
                           (invoice_id, batch_no, grade, uom, num_packages, sn_from, sn_to, nett_wt, total_qty, description, received_packages, received_packets, packets_sent) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (invoice_id, i.get('batch_no', 'MANUAL'), i['grade'], 'KG', i['received_bags'], 
                         i.get('sn_from', 0), i.get('sn_to', 0), i.get('nett_wt', 0), i.get('total_qty', 0), i.get('description', ''), i['received_bags'], i['received_packets'], i.get('packets_sent', 0)))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/invoice/header/<int:id>')
def get_invoice_header(id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM invoices WHERE id = ?', (id,)).fetchone()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({})


# --- EMAIL REPORTING SYSTEM ---

def clean_for_pdf(text):
    REPLACE = {
        "—": "-", "–": "-",
        "“": '"', "”": '"',
        "‘": "'", "’": "'",
        "•": "-", "●": "-",
        "₹": "Rs."
    }
    for bad, good in REPLACE.items():
        text = text.replace(bad, good)
    return "".join(ch for ch in text if ord(ch) <= 0xFFFF)

def create_report_pdf(summary_text):
    if FPDF is None:
        return None
        
    REPORT_DIR = os.path.join(os.getcwd(), "reports")
    os.makedirs(REPORT_DIR, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', size=16)
    pdf.set_text_color(12, 41, 75)
    pdf.cell(0, 15, "Factory Transfer - Daily Report", ln=True, align="C")
    pdf.line(20, 25, 190, 25)
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, clean_for_pdf(summary_text))

    filename = os.path.join(
        REPORT_DIR,
        f"Daily_Transfer_Report_{datetime.datetime.now().strftime('%Y%j_%H%M')}.pdf"
    )
    pdf.output(filename)
    return filename

@app.route('/send_daily_report')
def send_daily_report():
    if 'username' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    today_str = datetime.datetime.now().strftime('%d/%m/%Y')
    
    # Fetch Data
    sent_invoices = conn.execute("SELECT * FROM invoices WHERE date = ? AND invoice_no LIKE 'TRF-%'", (today_str,)).fetchall()
    received_invoices = conn.execute("SELECT * FROM invoices WHERE received_date = ?", (today_str,)).fetchall()
    dispatched_invoices = conn.execute("SELECT * FROM invoices WHERE date = ? AND invoice_no LIKE 'DIS-%'", (today_str,)).fetchall()
    
    summary_data = conn.execute('''
        SELECT 
            t.grade,
            SUM(CASE WHEN i.received_date = ? THEN t.received_packages ELSE 0 END) as bags_count,
            SUM(CASE WHEN i.received_date = ? THEN t.received_packages * t.nett_wt ELSE 0 END) as bags_weight,
            SUM(CASE WHEN i.invoice_no LIKE 'DIS-%' AND i.date = ? THEN t.received_packets ELSE 0 END) as pkts_count,
            SUM(CASE WHEN i.invoice_no LIKE 'DIS-%' AND i.date = ? THEN t.received_packets * t.nett_wt ELSE 0 END) as pkts_weight
        FROM transfer_items t
        JOIN invoices i ON t.invoice_id = i.id
        WHERE (i.date = ? OR i.received_date = ?)
        GROUP BY t.grade
        HAVING bags_count > 0 OR pkts_count > 0
    ''', (today_str, today_str, today_str, today_str, today_str, today_str)).fetchall()
    conn.close()

    # Generate Text Summary
    date_display = datetime.datetime.now().strftime("%d %B %Y")
    summary = f"FACTORY TRANSFER - DAILY ACTIVITY REPORT ({date_display})\n"
    summary += "="*70 + "\n\n"

    summary += f"1. INVOICES SENT TODAY:\n" + "-"*35 + "\n"
    if sent_invoices:
        for inv in sent_invoices:
            summary += f"• Inv: {inv['invoice_no']} | Status: {inv['status']} | Bags: {inv['total_packages']} | Qty: {inv['total_qty']} KG\n"
    else:
        summary += "No invoices sent today.\n"
    summary += "\n"

    summary += f"2. INVOICES RECEIVED TODAY:\n" + "-"*35 + "\n"
    if received_invoices:
        for inv in received_invoices:
            summary += f"• Inv: {inv['invoice_no']} | From: {inv['user']} | Bags Rec: {inv['total_received_bags']}\n"
    else:
        summary += "No invoices received today.\n"
    summary += "\n"

    summary += f"3. DISPATCHES TODAY (PACKETS):\n" + "-"*35 + "\n"
    if dispatched_invoices:
        for inv in dispatched_invoices:
            summary += f"• Inv: {inv['invoice_no']} | Items: {inv['total_items']} | Qty: {inv['total_qty']} KG\n"
    else:
        summary += "No packet dispatches today.\n"
    summary += "\n"

    summary += "4. GRADE-WISE ACTIVITY SUMMARY:\n" + "-"*40 + "\n"
    summary += f"{'Grade':<15} | {'Bags Rec. [kgs]':<20} | {'Pkts Disp. [no][kgs]':<25}\n"
    summary += "-"*65 + "\n"
    if summary_data:
        for g in summary_data:
            bags_rec = f"{g['bags_count']} [{g['bags_weight']:.2f}kg]"
            pkts_disp = f"{g['pkts_count']} [{g['pkts_weight']:.2f}kg]"
            summary += f"{g['grade']:<15} | {bags_rec:<20} | {pkts_disp:<25}\n"
    else:
        summary += "No summarized activity recorded today.\n"
    
    summary += "\n" + "="*70 + "\n"
    summary += "END OF DAILY ACTIVITY REPORT\n"

    # Email Logic
    sender = "maplepro2323@gmail.com"
    password = "vkah llvc mduj yfze"
    receiver = "24bcs228@kgcas.com"

    msg = MIMEMultipart()
    msg["Subject"] = f"Daily Factory Transfer Report - {today_str}"
    msg["From"] = f"Transfer Software <{sender}>"
    msg["To"] = receiver
    msg.attach(MIMEText(summary, "plain"))

    try:
        pdf_file = create_report_pdf(summary)
        if pdf_file and os.path.exists(pdf_file):
            with open(pdf_file, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=os.path.basename(pdf_file))
                msg.attach(part)
    except Exception as e:
        print(f"PDF Error: {e}")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        return jsonify({"status": "success", "message": "Email sent successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to send email: {str(e)}"})

@app.route('/api/invoice/delete/<int:invoice_id>', methods=['DELETE'])
def delete_invoice(invoice_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        # Delete children items first
        conn.execute('DELETE FROM transfer_items WHERE invoice_id = ?', (invoice_id,))
        # Delete parent invoice
        conn.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/invoice/update_manual/<int:invoice_id>', methods=['POST'])
def update_manual_invoice(invoice_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        items = data.get('items', [])
        total_items = len(items)
        # Handle both types of quantity fields (received vs sent)
        total_packages = sum(int(i.get('received_bags', i.get('num_packages', 0))) for i in items)
        total_packets = sum(int(i.get('received_packets', 0)) for i in items)
        total_qty = sum(float(i.get('total_qty', 0)) for i in items)
        manual_sno = data.get('manual_sno')

        # Update parent invoice
        cur.execute('''UPDATE invoices SET total_items = ?, total_qty = ?, total_packages = ?, 
                       received_packets = ?, total_received_bags = ?, manual_sno = ? WHERE id = ?''',
                    (total_items, total_qty, total_packages, total_packets, total_packages, manual_sno, invoice_id))
        
        # Delete old items and insert fresh ones
        cur.execute('DELETE FROM transfer_items WHERE invoice_id = ?', (invoice_id,))
        
        for i in items:
            # We use 'MANUAL' or i.get('batch_no')
            batch = i.get('batch_no', 'MANUAL')
            cur.execute('''INSERT INTO transfer_items 
                           (invoice_id, batch_no, grade, uom, num_packages, sn_from, sn_to, nett_wt, total_qty, description, received_packages, received_packets, packets_sent) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (invoice_id, batch, i['grade'], 'KG', i.get('received_bags', i.get('num_packages', 0)), 
                         i.get('sn_from', 0), i.get('sn_to', 0), i.get('nett_wt', 0), i.get('total_qty', 0), i.get('description', ''), 
                         i.get('received_bags', i.get('num_packages', 0)), i.get('received_packets', 0), i.get('packets_sent', 0)))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


if __name__ == "__main__":
    run_flask()
