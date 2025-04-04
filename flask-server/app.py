from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'exp3'

mysql = MySQL(app)

EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
print(f"Email config loaded: {EMAIL_ADDRESS}, {EMAIL_PASSWORD}")

@app.route('/')
def index():
    msg = "Welcome to the Food Waste Prevention Platform!"
    return render_template('index.html', msg=msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'user_name' in request.form and 'password' in request.form:
        user_name = request.form['user_name']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM user_login WHERE user_name = %s AND password = %s', (user_name, hashed_password,))
        account = cursor.fetchone()
        
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['user_name']
            session['role'] = account['role']
            return redirect(url_for('index'))
        else:
            msg = 'Incorrect username or password!'
        
        cursor.close()
    
    success = request.args.get('success', 'false')
    return render_template('login.html', msg=msg, success=success)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and all(key in request.form for key in ['user_name', 'password', 'confirm_password', 'email', 'role']):
        user_name = request.form['user_name']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']
        role = int(request.form['role'])

        if password != confirm_password:
            msg = 'Passwords do not match!'
        else:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM user_login WHERE user_name = %s', (user_name,))
            account = cursor.fetchone()

            if account:
                msg = 'Account already exists!'
            elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                msg = 'Invalid email address!'
            elif not re.match(r'[A-Za-z0-9]+', user_name):
                msg = 'Username must contain only characters and numbers!'
            elif role not in [0, 1]:
                msg = 'Invalid role selected!'
            else:
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                cursor.execute(
                    'INSERT INTO user_login (user_name, email, password, role) VALUES (%s, %s, %s, %s)',
                    (user_name, email, hashed_password, role)
                )
                mysql.connection.commit()
                cursor.close()
                return redirect(url_for('login', success='true'))

            cursor.close()
    elif request.method == 'POST':
        msg = 'Please fill out all fields!'
    
    return render_template('register.html', msg=msg)

@app.route('/food_waste_management', methods=['GET', 'POST'])
def food_waste_management():
    if 'loggedin' not in session or not session['loggedin']:
        return redirect(url_for('login'))
    
    msg = ''
    if session['role'] == 0:  # Organizer
        if request.method == 'POST' and all(key in request.form for key in ['food_names', 'quantity']):
            food_names = request.form['food_names']
            quantity = request.form['quantity']
            
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute(
                'INSERT INTO food_offers (user_id, food_names, quantity, status) VALUES (%s, %s, %s, %s)',
                (session['id'], food_names, quantity, 'pending')
            )
            mysql.connection.commit()
            offer_id = cursor.lastrowid
            
            cursor.execute('SELECT email FROM user_login WHERE role = 1')
            ngo_emails = [row['email'] for row in cursor.fetchall()]
            cursor.close()
            
            print(f"NGO emails found: {ngo_emails}")
            if not ngo_emails:
                msg = 'Food offer submitted, but no NGOs available to notify.'
            else:
                subject = f"New Food Donation Available from {session['username']}"
                body = f"""
                Dear NGO,

                A new food donation is available:
                - Food Names: {food_names}
                - Quantity: {quantity}
                - Offer ID: {offer_id}

                Please log in to accept this offer: {url_for('food_waste_management', _external=True)}

                Regards,
                Food Waste Prevention Platform
                """
                
                for email in ngo_emails:
                    send_email(email, subject, body)
                msg = 'Food offer submitted successfully! NGOs have been notified.'
        
        return render_template('food_waste_management.html', msg=msg, role=session['role'])
    
    elif session['role'] == 1:  # NGO
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT fo.id, fo.food_names, fo.quantity, ul.user_name AS username
            FROM food_offers fo
            JOIN user_login ul ON fo.user_id = ul.id
            WHERE fo.status = 'pending'
        """)
        offers = cursor.fetchall()
        cursor.close()
        return render_template('food_waste_management.html', msg=msg, role=session['role'], offers=offers)

@app.route('/accept_offer/<int:offer_id>', methods=['POST'])
def accept_offer(offer_id):
    if 'loggedin' not in session or not session['loggedin'] or session['role'] != 1:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('UPDATE food_offers SET status = %s WHERE id = %s AND status = %s', ('accepted', offer_id, 'pending'))
    mysql.connection.commit()
    rows_affected = cursor.rowcount
    cursor.close()
    
    if rows_affected > 0:
        msg = f"Offer {offer_id} accepted successfully!"
    else:
        msg = "Offer already accepted or not found."
    
    return redirect(url_for('food_waste_management', msg=msg))

@app.route('/about')
def about():
    msg = "About Food Waste Prevention Platform: Our mission is to reduce food waste by connecting event organizers with NGOs to donate surplus food."
    return render_template('about.html', msg=msg)

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('index'))

def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent successfully to {to_email}")
    except smtplib.SMTPAuthenticationError:
        print(f"Authentication failed for {EMAIL_ADDRESS}. Check EMAIL_ADDRESS and EMAIL_PASSWORD.")
    except smtplib.SMTPException as e:
        print(f"SMTP error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.quit()
    print("SMTP login test successful")
except Exception as e:
    print(f"SMTP login test failed: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)