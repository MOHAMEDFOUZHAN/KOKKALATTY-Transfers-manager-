import os
import sqlite3
import datetime
import threading
import webbrowser
import time
import random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import sys
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

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

def find_available_port(start_port=5003):
    import socket
    port = start_port
    while port < start_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    return start_port

def run_flask():
    port = find_available_port(5003)
    server_url = f"http://127.0.0.1:{port}"
    print(f"Starting Kokkalatty Transfers server on {server_url}...")
    
    # Run the server in a separate thread
    def start_server():
        try:
            from waitress import serve
            serve(app, host="127.0.0.1", port=port, threads=6)
        except Exception as e:
            print(f"Waitress notice ({e}), running with Flask server...")
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
            
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Wait for server to initialize
    time.sleep(1.2)
    
    gui_launched = False
    try:
        import webview
        print("Launching desktop window...")
        webview.create_window('Kokkalatty Transfers Manager', server_url, width=1280, height=850, min_size=(900, 600))
        webview.start()
        gui_launched = True
    except Exception as e:
        print(f"Desktop window notice ({e}). Opening in default browser instead...")
    
    if not gui_launched:
        webbrowser.open(server_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

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
            template_folder=resource_path('branch1/templates'),
            static_folder=resource_path('static'))

# Configure multi-folder template loading
template_loaders = []
for p in [resource_path('templates'), resource_path('branch1/templates'), resource_path('branch2/templates'), resource_path('.')]:
    if os.path.exists(p):
        template_loaders.append(FileSystemLoader(p))
app.jinja_loader = ChoiceLoader(template_loaders)

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
    try:
        conn.execute('ALTER TABLE branch1_transfers ADD COLUMN gate_pass_no TEXT')
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
    
    conn.execute('''CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
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

def get_app_setting(key, default=''):
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
        conn.close()
        return row['value'] if row and row['value'] is not None else default
    except:
        return default

def set_app_setting(key, value):
    conn = get_db_connection()
    conn.execute('INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

# Seed default settings
def seed_settings():
    defaults = {
        'sender_email': 'maplepro2323@gmail.com',
        'sender_password': 'vkah llvc mduj yfze',
        'receiver_email': '24bcs228@kgcas.com',
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': '587',
        'whatsapp_phone': ''
    }
    conn = get_db_connection()
    for k, v in defaults.items():
        conn.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', (k, v))
    conn.commit()
    conn.close()

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
seed_settings()

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
            MIN(gate_pass_no) as gate_pass_no,
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
        gate_pass_no = data.get('gate_pass_no', '')

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
                           (sl_no, grade, batch_invoice_no, hsn_code, no_of_packages, serial_from, serial_to, net_weight_kgs, total_qty_kg, entry_date, entry_time, group_id, destination_name, destination_address, destination_gstin, vehicle_no, gross_weight, bag_weight, unit_weight, driver_name, driver_no, gate_pass_no)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (item['slNo'], item['grade'], item['batch'], item.get('hsn', ''), item['pkgs'], 
                         item['snFrom'], item['snTo'], item['netWt'], item['totalQty'], date_str, time_str, group_id, dest_name, dest_addr, dest_gstin, vehicle_no, item.get('grossWt'), item.get('bagWt'), item.get('unitWt'), driver_name, driver_no, gate_pass_no))
        
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
        return jsonify({'last_serial': 0, 'last_gate_pass': ''}), 403
    conn = get_db_connection()
    row = conn.execute('SELECT MAX(serial_to) as last_val FROM branch1_transfers').fetchone()
    gp_row = conn.execute('SELECT gate_pass_no FROM branch1_transfers WHERE gate_pass_no IS NOT NULL AND gate_pass_no != "" ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    last_val = row['last_val'] if row and row['last_val'] else 0
    last_gp = gp_row['gate_pass_no'] if gp_row and gp_row['gate_pass_no'] else ''
    return jsonify({'last_serial': last_val, 'last_gate_pass': last_gp})


# --- PDF GENERATION & WHATSAPP INTEGRATION ---

def generate_challan_pdf(group_id):
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM branch1_transfers WHERE group_id = ? ORDER BY sl_no ASC, id ASC', (group_id,)).fetchall()
    conn.close()
    
    if not items:
        return None, None, None

    first = items[0]
    gate_pass_no = first['gate_pass_no'] or ''
    date_str = first['entry_date'] or ''
    time_str = first['entry_time'] or ''
    consignee_name = first['destination_name'] or 'SELF'
    consignee_addr = first['destination_address'] or 'Kokkalatty Tea Traders, Ketty Palada'
    consignee_gstin = first['destination_gstin'] or '33AAQFK2881H1Z2'
    vehicle_no = first['vehicle_no'] or ''
    driver_name = first['driver_name'] or ''
    driver_no = first['driver_no'] or ''
    ref_no = first['batch_invoice_no'] or 'CHALLAN'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CompanyTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=1,
        textTransform='uppercase'
    )
    sub_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=1
    )
    bold_sub = ParagraphStyle(
        'BoldSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        alignment=1
    )
    doc_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        alignment=1
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=1
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=1
    )

    elements = []
    elements.append(Paragraph('KOKKALATTY TEA INDUSTRY', title_style))
    elements.append(Paragraph('KETTI PALADA NILGIRIS', sub_style))
    elements.append(Paragraph('<u>Admin off: # 16B , Holm Wood, Nankem Hospital Premises, Coonoor – 643101</u>', sub_style))
    elements.append(Paragraph('GST No.33AALFK7353D1ZE', bold_sub))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.black, spaceAfter=6, spaceBefore=2))
    elements.append(Paragraph('<u>DELIVERY CHALLAN</u>', doc_title))
    elements.append(Spacer(1, 8))

    # Meta row
    meta_data = [
        [
            Paragraph(f'<b>Gate pass No:</b> {gate_pass_no or "____"}', styles['Normal']),
            Paragraph(f'<b>Date Of Despatch:</b> {date_str}', styles['Normal']),
            Paragraph(f'<b>Time of Despatch:</b> {time_str}', styles['Normal'])
        ]
    ]
    meta_table = Table(meta_data, colWidths=[180, 185, 190])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 6))

    # Consignee box
    display_addr = consignee_addr
    if 'tea park' in consignee_name.lower():
        display_addr += '<br/>For Coonoor Auction Sales through M/s. Paramount Tea Marketing (SI) Pvt Ltd. Coonoor'

    consignee_p = Paragraph(
        f'<b>Name & Address of the Consignee:</b> <b>{consignee_name}</b><br/>'
        f'{display_addr}<br/>'
        f'<b>GST No.:</b> {consignee_gstin}',
        styles['Normal']
    )
    consignee_table = Table([[consignee_p]], colWidths=[555])
    consignee_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)
    ]))
    elements.append(consignee_table)
    elements.append(Spacer(1, 8))

    # Items table
    headers = [
        Paragraph('<b>Sl.No</b>', cell_bold),
        Paragraph('<b>Grade</b>', cell_bold),
        Paragraph('<b>No Of<br/>Pkgs</b>', cell_bold),
        Paragraph('<b>Invoice No</b>', cell_bold),
        Paragraph('<b>Sl.From</b>', cell_bold),
        Paragraph('<b>Sl.To</b>', cell_bold),
        Paragraph('<b>Unit Wt</b>', cell_bold),
        Paragraph('<b>Gross Wt<br/>(Tea)</b>', cell_bold),
        Paragraph('<b>Net Wt<br/>(+Bag)</b>', cell_bold),
        Paragraph('<b>HSN</b>', cell_bold)
    ]
    table_data = [headers]

    tot_pkgs = 0
    tot_gross = 0.0
    tot_net = 0.0
    grades_list = []

    for idx, item in enumerate(items, 1):
        pkgs = int(item['no_of_packages'] or 0)
        unit_wt = float(item['unit_weight'] or 0.0)
        gross_wt = float(item['gross_weight'] or 0.0)
        net_wt = float(item['total_qty_kg'] or item['net_weight_kgs'] or 0.0)
        grade = item['grade'] or ''
        if grade and grade not in grades_list:
            grades_list.append(grade)

        tot_pkgs += pkgs
        tot_gross += gross_wt
        tot_net += net_wt

        table_data.append([
            Paragraph(str(item['sl_no'] or idx), cell_style),
            Paragraph(grade, cell_style),
            Paragraph(str(pkgs), cell_style),
            Paragraph(str(item['batch_invoice_no'] or ''), cell_style),
            Paragraph(str(item['serial_from'] or ''), cell_style),
            Paragraph(str(item['serial_to'] or ''), cell_style),
            Paragraph(f"{unit_wt:.2f}" if unit_wt else '', cell_style),
            Paragraph(f"{gross_wt:.2f}", cell_style),
            Paragraph(f"{net_wt:.2f}", cell_style),
            Paragraph(str(item['hsn_code'] or ''), cell_style),
        ])

    # Total row
    table_data.append([
        Paragraph('<b>TOTAL:</b>', cell_bold),
        '',
        Paragraph(f'<b>{tot_pkgs}</b>', cell_bold),
        '', '', '', '',
        Paragraph(f'<b>{tot_gross:.2f}</b>', cell_bold),
        Paragraph(f'<b>{tot_net:.2f}</b>', cell_bold),
        ''
    ])

    items_table = Table(table_data, colWidths=[35, 60, 48, 80, 45, 45, 45, 67, 70, 60])
    items_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
        ('SPAN', (0,-1), (1,-1)),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 8))

    # Statutory Declaration
    dec_style = ParagraphStyle(
        'DecStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        alignment=4 # Justify
    )
    dec_text = (
        '<b>DECLARATION:</b> The Teas in the above Invoices were made from Green Leaf which have only used PPFs as '
        'recommended in Plant Protection Code and have not used any chemicals and pesticides banned in India. In the event '
        'of detection of any banned pesticides or chemicals and their residues are beyond the prescribed limit Tea Board is '
        'free to take appropriate action as per the provisions of the Tea Marketing (Control) Order, 2003.'
    )
    dec_table = Table([[Paragraph(dec_text, dec_style)]], colWidths=[555])
    dec_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(dec_table)
    elements.append(Spacer(1, 8))

    # Manner of transport
    manner_parts = []
    if driver_name:
        manner_parts.append(driver_name.upper())
    if vehicle_no:
        manner_parts.append(vehicle_no.upper())
    manner_str = f"BY {', '.join(manner_parts)}" if manner_parts else "BY ________________________"

    transport_data = [
        [
            Paragraph(f'<b>MANNER OF TRANSPORT:</b> {manner_str}', styles['Normal'])
        ]
    ]
    trans_table = Table(transport_data, colWidths=[555])
    trans_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(trans_table)
    elements.append(Spacer(1, 26))

    # Signatures
    sig_style_left = ParagraphStyle(
        'SigLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#002B49'),
        alignment=0
    )
    sig_style_right = ParagraphStyle(
        'SigRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#002B49'),
        alignment=2
    )
    sig_data = [
        [
            Paragraph('<b>SIGNATURE OF THE DRIVER</b>', sig_style_left),
            Paragraph('<b>SIGNATURE OF THE<br/>OWNER/ MANAGER</b>', sig_style_right)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[275, 280])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0)
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    filename = f"Delivery_Challan_{ref_no.replace('/', '_').replace(' ', '_')}.pdf"

    metadata = {
        'group_id': group_id,
        'ref_no': ref_no,
        'gate_pass_no': gate_pass_no,
        'date': date_str,
        'time': time_str,
        'consignee': consignee_name,
        'consignee_address': consignee_addr,
        'vehicle_no': vehicle_no,
        'driver_name': driver_name,
        'driver_no': driver_no,
        'total_packages': tot_pkgs,
        'total_qty': f"{tot_net:.2f}",
        'grades': ", ".join(grades_list),
        'pdf_filename': filename
    }

    return buffer, filename, metadata


@app.route('/api/branch1/transfer/pdf/<group_id>')
def download_branch1_challan_pdf(group_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    buffer, filename, metadata = generate_challan_pdf(group_id)
    if not buffer:
        return jsonify({'success': False, 'message': 'Transfer record not found'}), 404

    as_attachment = (request.args.get('download') == '1')
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=as_attachment,
        download_name=filename
    )


@app.route('/api/branch1/transfer/summary/<group_id>')
def get_branch1_transfer_summary(group_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM branch1_transfers WHERE group_id = ? ORDER BY sl_no ASC, id ASC', (group_id,)).fetchall()
    conn.close()

    if not items:
        return jsonify({'success': False, 'message': 'Transfer record not found'}), 404

    first = items[0]
    grades_list = []
    tot_pkgs = 0
    tot_net = 0.0

    for item in items:
        g = item['grade'] or ''
        if g and g not in grades_list:
            grades_list.append(g)
        tot_pkgs += int(item['no_of_packages'] or 0)
        tot_net += float(item['total_qty_kg'] or item['net_weight_kgs'] or 0.0)

    default_wa = get_app_setting('whatsapp_phone', '')
    dest_phone = first['driver_no'] or default_wa
    gp = first['gate_pass_no'] or ''

    summary = {
        'success': True,
        'group_id': group_id,
        'ref_no': first['batch_invoice_no'] or 'CHALLAN',
        'gate_pass_no': gp,
        'date': first['entry_date'] or '',
        'time': first['entry_time'] or '',
        'consignee': first['destination_name'] or 'SELF',
        'vehicle_no': first['vehicle_no'] or 'N/A',
        'driver_name': first['driver_name'] or 'N/A',
        'driver_no': first['driver_no'] or '',
        'suggested_phone': dest_phone,
        'total_packages': tot_pkgs,
        'total_qty': f"{tot_net:.2f}",
        'grades': ", ".join(grades_list),
        'pdf_url': f"/api/branch1/transfer/pdf/{group_id}?download=1"
    }

    # WhatsApp formatted message
    gp_line = f"🎫 *Gate Pass No:* {gp}\n" if gp else ""
    summary['whatsapp_text'] = (
        f"🍵 *Kokkalatty Tea Industry - Delivery Challan*\n"
        f"{gp_line}"
        f"📄 *Ref / Challan No:* {summary['ref_no']}\n"
        f"📅 *Date:* {summary['date']} {summary['time']}\n"
        f"🏢 *Consignee:* {summary['consignee']}\n"
        f"🚚 *Vehicle No:* {summary['vehicle_no']}\n"
        f"👤 *Driver:* {summary['driver_name']}" + (f" ({summary['driver_no']})" if summary['driver_no'] else "") + "\n"
        f"📦 *Total Packages:* {summary['total_packages']} Bags\n"
        f"⚖️ *Total Net Qty:* {summary['total_qty']} KG\n"
        f"🏷️ *Grades:* {summary['grades']}\n"
        f"📎 *Official Challan PDF Attached*"
    )

    return jsonify(summary)


# --- EMAIL SETTINGS MANAGEMENT ---

@app.route('/api/settings/email', methods=['GET', 'POST'])
def manage_email_settings():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    if request.method == 'POST':
        data = request.json or {}
        if 'sender_email' in data:
            set_app_setting('sender_email', data['sender_email'].strip())
        if 'sender_password' in data and data['sender_password'].strip():
            set_app_setting('sender_password', data['sender_password'].strip())
        if 'receiver_email' in data:
            set_app_setting('receiver_email', data['receiver_email'].strip())
        if 'smtp_host' in data:
            set_app_setting('smtp_host', data['smtp_host'].strip())
        if 'smtp_port' in data:
            set_app_setting('smtp_port', str(data['smtp_port']).strip())
        if 'whatsapp_phone' in data:
            set_app_setting('whatsapp_phone', data['whatsapp_phone'].strip())
        return jsonify({'success': True, 'message': 'Email & WhatsApp settings saved successfully!'})

    current_pw = get_app_setting('sender_password', '')
    return jsonify({
        'sender_email': get_app_setting('sender_email', 'maplepro2323@gmail.com'),
        'has_password': bool(current_pw),
        'receiver_email': get_app_setting('receiver_email', '24bcs228@kgcas.com'),
        'smtp_host': get_app_setting('smtp_host', 'smtp.gmail.com'),
        'smtp_port': get_app_setting('smtp_port', '587'),
        'whatsapp_phone': get_app_setting('whatsapp_phone', '')
    })


@app.route('/api/settings/test_email', methods=['POST'])
def test_email_route():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json or {}
    # If custom values submitted with test, update or use them
    if data.get('sender_email'):
        set_app_setting('sender_email', data['sender_email'].strip())
    if data.get('sender_password'):
        set_app_setting('sender_password', data['sender_password'].strip())
    if data.get('receiver_email'):
        set_app_setting('receiver_email', data['receiver_email'].strip())

    now_str = datetime.datetime.now().strftime('%d/%m/%Y %I:%M %p')
    test_subject = f"Test Email - Kokkalatty Transfers Manager ({now_str})"
    test_body = (
        f"This is a verification email from Kokkalatty Transfers Manager.\n\n"
        f"Timestamp: {now_str}\n"
        f"Configured Sender: {get_app_setting('sender_email')}\n"
        f"Configured Receiver: {get_app_setting('receiver_email')}\n\n"
        f"If you received this message, your SMTP credentials and daily report mailer are working correctly!"
    )

    success, message = send_email_via_smtp(test_subject, test_body)
    return jsonify({'success': success, 'message': message})


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

def send_email_via_smtp(subject, body_text, attachment_path=None):
    sender = get_app_setting('sender_email', 'maplepro2323@gmail.com').strip()
    raw_password = get_app_setting('sender_password', '').strip()
    password = raw_password.replace(" ", "")
    receiver = get_app_setting('receiver_email', '24bcs228@kgcas.com').strip()
    smtp_host = get_app_setting('smtp_host', 'smtp.gmail.com').strip()
    smtp_port_str = get_app_setting('smtp_port', '587').strip()
    try:
        smtp_port = int(smtp_port_str)
    except:
        smtp_port = 587

    if not sender or not password or not receiver:
        return False, "Email sender, password, or recipient not configured. Please open Settings to configure."

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"Kokkalatty Transfer Software <{sender}>"
    msg["To"] = receiver
    msg.attach(MIMEText(body_text, "plain"))

    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=os.path.basename(attachment_path))
                msg.attach(part)
        except Exception as ex:
            print(f"Attachment error: {ex}")

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12)
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
        return True, f"Email sent successfully to {receiver}!"
    except smtplib.SMTPAuthenticationError as auth_err:
        err_str = str(auth_err)
        if '534' in err_str or 'WebLoginRequired' in err_str:
            return False, "Google Authentication Error (534): Google requires a valid App Password. Please generate a new 16-character App Password at https://myaccount.google.com/apppasswords and save it in Settings."
        return False, f"Email Authentication Failed: Username or App Password incorrect. ({err_str})"
    except smtplib.SMTPResponseException as resp_err:
        if resp_err.smtp_code == 534:
            return False, "Google Authentication Error (534): Google requires a valid App Password. Please generate a new 16-character App Password at https://myaccount.google.com/apppasswords and save it in Settings."
        return False, f"Mail Server Error ({resp_err.smtp_code}): {resp_err.smtp_error}"
    except smtplib.SMTPServerDisconnected:
        return False, "Mail server disconnected unexpectedly. This usually happens when Gmail rejects the app password or port is blocked. Please check your App Password in Settings."
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


@app.route('/send_daily_report')
def send_daily_report():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    conn = get_db_connection()
    today_str = datetime.datetime.now().strftime('%d/%m/%Y')
    date_display = datetime.datetime.now().strftime("%d %B %Y")
    username = session.get('username')

    if username == 'branch1':
        # Branch 1 Daily Report
        transfers = conn.execute('''
            SELECT group_id, entry_date, entry_time,
                   MIN(batch_invoice_no) as ref_no,
                   MIN(destination_name) as dest_name,
                   MIN(vehicle_no) as vehicle_no,
                   MIN(driver_name) as driver_name,
                   COUNT(*) as item_count,
                   SUM(no_of_packages) as total_packages,
                   SUM(total_qty_kg) as grand_total_qty,
                   GROUP_CONCAT(DISTINCT grade) as grades
            FROM branch1_transfers
            WHERE entry_date = ?
            GROUP BY group_id
            ORDER BY id DESC
        ''', (today_str,)).fetchall()

        productions = conn.execute('''
            SELECT * FROM branch1_production WHERE date = ? ORDER BY id DESC
        ''', (today_str,)).fetchall()

        grade_summary = conn.execute('''
            SELECT grade,
                   SUM(no_of_packages) as total_pkgs,
                   SUM(total_qty_kg) as total_wt
            FROM branch1_transfers
            WHERE entry_date = ?
            GROUP BY grade
        ''', (today_str,)).fetchall()

        conn.close()

        # Generate Text Summary
        summary = f"KOKKALATTY TEA INDUSTRY - BRANCH 1 DAILY REPORT\n"
        summary += f"Date: {date_display}\n"
        summary += "=" * 70 + "\n\n"

        summary += f"1. TRANSFERS DISPATCHED TODAY ({today_str}):\n" + "-" * 45 + "\n"
        if transfers:
            for t in transfers:
                summary += f"• Ref: {t['ref_no']} | To: {t['dest_name'] or 'SELF'} | Veh: {t['vehicle_no'] or 'N/A'} | Driver: {t['driver_name'] or 'N/A'}\n"
                summary += f"  Packages: {t['total_packages']} Bags | Qty: {t['grand_total_qty']} KG | Grades: {t['grades']}\n\n"
        else:
            summary += "No transfers recorded today.\n\n"

        summary += f"2. PRODUCTION LOGGED TODAY ({today_str}):\n" + "-" * 45 + "\n"
        if productions:
            for p in productions:
                summary += f"• Batch: {p['batch_no'] or 'N/A'} | Grade: {p['grade']} | Produced: {p['qty_produced']} {p['uom'] or 'KG'} | Packages: {p['no_of_packages'] or 0}\n"
            summary += "\n"
        else:
            summary += "No production recorded today.\n\n"

        summary += f"3. DISPATCH GRADE-WISE SUMMARY:\n" + "-" * 45 + "\n"
        summary += f"{'Grade':<15} | {'Packages (Bags)':<18} | {'Weight (KG)':<15}\n"
        summary += "-" * 55 + "\n"
        if grade_summary:
            for g in grade_summary:
                summary += f"{g['grade']:<15} | {g['total_pkgs']:<18} | {g['total_wt']:<15.2f}\n"
        else:
            summary += "No grade dispatch recorded today.\n"

        summary += "\n" + "=" * 70 + "\n"
        summary += "END OF BRANCH 1 DAILY REPORT\n"

        pdf_file = create_report_pdf(summary)
        success, message = send_email_via_smtp(f"Kokkalatty Branch 1 Daily Report - {today_str}", summary, pdf_file)
        return jsonify({"status": "success" if success else "error", "message": message})

    else:
        # Branch 2 / Default Report
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

        pdf_file = create_report_pdf(summary)
        success, message = send_email_via_smtp(f"Daily Factory Transfer Report - {today_str}", summary, pdf_file)
        return jsonify({"status": "success" if success else "error", "message": message})

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
