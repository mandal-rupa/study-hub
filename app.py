import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, g
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'database.db')
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'replace_this_with_a_secure_random_key'


# Database helpers

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # resources: stores study notes and PYQs (is_pyq 0/1)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year TEXT,
        branch TEXT,
        semester TEXT,
        subject TEXT,
        chapter TEXT,
        filename TEXT,
        is_pyq INTEGER DEFAULT 0,
        uploaded_by TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # users (very simple)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    ''')

# create default admin if not exists (SECURE)
    cur.execute(
        "INSERT OR IGNORE INTO users (username,password,role) VALUES (?,?,?)",
        (
            "admin",
            generate_password_hash("HiT@Admin#2026"),
            "admin"
        )
    )
# except Exception:
#     pass
    conn.commit()
    conn.close()
     
init_db()


# Utilities

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes

@app.route("/")
def index():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM resources
        ORDER BY id DESC
        LIMIT 3
    """)
    recent_resources = cur.fetchall()
    conn.close()

    return render_template(
        "index.html",
        recent_resources=recent_resources
    )


@app.route('/resources', methods=['GET', 'POST'])
def resources():
    conn = get_db_connection()
    cur = conn.cursor()

    # filter defaults (show all)
    year = request.values.get('year') or ''
    branch = request.values.get('branch') or ''
    semester = request.values.get('semester') or ''
    subject = request.values.get('subject') or ''

    query = "SELECT * FROM resources WHERE 1=1"
    params = []
    if year:
        query += " AND year = ?"
        params.append(year)
    if branch:
        query += " AND branch = ?"
        params.append(branch)
    if semester:
        query += " AND semester = ?"
        params.append(semester)
    if subject:
        query += " AND subject LIKE ?"
        params.append('%' + subject + '%')

    query += " ORDER BY uploaded_at DESC"

    cur.execute(query, params)
    rows = cur.fetchall()

    conn.close()
    return render_template('resources.html', resources=rows, filters={'year':year,'branch':branch,'semester':semester,'subject':subject})

@app.route('/pyqs')
def pyqs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM resources WHERE is_pyq=1 ORDER BY subject, uploaded_at DESC")
    rows = cur.fetchall()
    conn.close()
    return render_template('pyqs.html', pyqs=rows)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # only allow admin (simple session-based)
    if 'user' not in session or session.get('role') != 'admin':
        flash('Admin login required to upload.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        year = request.form.get('year','')
        branch = request.form.get('branch','')
        semester = request.form.get('semester','')
        subject = request.form.get('subject','')
        chapter = request.form.get('chapter','')
        author = request.form.get('author')
        is_pyq = 1 if request.form.get('is_pyq') == 'on' else 0
        file = request.files.get('file')

        if not file or file.filename == '':
            flash('Please choose a PDF file.', 'error')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('Only PDF files allowed.', 'error')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        # to avoid collisions, prefix with timestamp
        import time
        filename = f"{int(time.time())}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        # print("UPLOAD DATA:", year, branch, semester, subject, chapter, author, is_pyq)
        # print("FILENAME:", filename)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            '''
            INSERT INTO resources
            (year, branch, semester, subject, chapter, filename, is_pyq, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
               year,
               branch,
               semester,
               subject,
               chapter,
               filename,
               is_pyq,
               author
            )
        )
        conn.commit()
        conn.close()
        flash('File uploaded successfully.', 'success')
        return redirect(url_for('upload'))
    return render_template('upload.html')

@app.route('/delete/<int:rid>')
def delete_resource(rid):

    # sirf admin ko allow
    if 'user' not in session or session.get('role') != 'admin':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    # filename lao
    cur.execute("SELECT filename FROM resources WHERE id=?", (rid,))
    row = cur.fetchone()

    if row:
        filename = row['filename']

        # DB se delete
        cur.execute("DELETE FROM resources WHERE id=?", (rid,))
        conn.commit()

        # uploads folder se file delete
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        flash('Resource deleted successfully.', 'success')

    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/edit/<int:rid>', methods=['GET', 'POST'])
def edit_resource(rid):
    # sirf admin
    if 'user' not in session or session.get('role') != 'admin':
        flash('Admin login required.', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # existing resource lao
    cur.execute("SELECT * FROM resources WHERE id=?", (rid,))
    resource = cur.fetchone()

    if not resource:
        conn.close()
        flash('Resource not found.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        subject  = request.form.get('subject', '')
        chapter  = request.form.get('chapter', '')
        author   = request.form.get('author', '')
        branch   = request.form.get('branch', '')
        semester = request.form.get('semester', '')
        year     = request.form.get('year', '')

        cur.execute("""
            UPDATE resources
            SET subject=?, chapter=?, uploaded_by=?, branch=?, semester=?, year=?
            WHERE id=?
        """, (subject, chapter, author, branch, semester, year, rid))

        conn.commit()
        conn.close()

        flash('Resource updated successfully.', 'success')
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit_resource.html', r=resource)




@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
           session['user'] = user['username']
           session['role'] = user['role']
           flash('Logged in successfully.', 'success')
           return redirect(url_for('index'))
        else:
           flash('Invalid credentials.', 'error')
           return redirect(url_for('login'))
    return render_template('login.html')
       
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
