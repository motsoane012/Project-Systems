from flask import Flask, request, jsonify, render_template
from flask_mysqldb import MySQL
from flask_cors import CORS
import hashlib
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ==========================
# DATABASE CONFIG
# ==========================
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password/123'
app.config['MYSQL_DB'] = 'motorspare_db'

mysql = MySQL(app)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================
# SERVE FRONTEND
# ==========================
@app.route('/')
def home():
    return render_template("motorspare.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# ============================================================
# PARTS (INVENTORY)
# ============================================================

@app.route('/parts', methods=['GET'])
def get_parts():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT part_id, name, type, condition_type, year, description,
               supplier_price, selling_price, qty, supplier_name, on_order, image_path
        FROM parts
    """)
    rows = cur.fetchall()
    cur.close()
    parts = []
    for r in rows:
        parts.append({
            "id":             r[0],
            "name":           r[1],
            "type":           r[2] or "",
            "condition":      r[3],
            "year":           r[4],
            "description":    r[5] or "",
            "supplier_price": float(r[6]),
            "price":          float(r[7]),
            "qty":            r[8],
            "supplier_name":  r[9] or "",
            "on_order":       bool(r[10]),
            "image":          r[11] or ""
        })
    return jsonify(parts)


@app.route('/add_part', methods=['POST'])
def add_part():
    d = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO parts (name, type, condition_type, year, description,
                           supplier_price, selling_price, qty, supplier_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        d.get('name'),
        d.get('type', ''),
        d.get('condition', 'New'),
        d.get('year') or None,
        d.get('description', ''),
        d.get('supplier_price', 0),
        d.get('selling_price', 0),
        d.get('qty', 0),
        d.get('supplier_name', '')
    ))
    mysql.connection.commit()
    part_id = cur.lastrowid
    cur.close()
    return jsonify({"message": "Part added successfully", "part_id": part_id})


@app.route('/update_part/<int:part_id>', methods=['PUT'])
def update_part(part_id):
    d = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE parts SET
            name           = %s,
            type           = %s,
            condition_type = %s,
            year           = %s,
            description    = %s,
            supplier_price = %s,
            selling_price  = %s,
            qty            = %s,
            supplier_name  = %s,
            on_order       = %s
        WHERE part_id = %s
    """, (
        d.get('name'),
        d.get('type', ''),
        d.get('condition', 'New'),
        d.get('year') or None,
        d.get('description', ''),
        d.get('supplier_price', 0),
        d.get('selling_price', 0),
        d.get('qty', 0),
        d.get('supplier_name', ''),
        d.get('on_order', False),
        part_id
    ))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Part updated successfully"})


@app.route('/delete_part/<int:part_id>', methods=['DELETE'])
def delete_part(part_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM parts WHERE part_id = %s", (part_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Part deleted successfully"})


@app.route('/set_selling_price/<int:part_id>', methods=['PUT'])
def set_selling_price(part_id):
    d = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("UPDATE parts SET selling_price = %s WHERE part_id = %s",
                (d.get('selling_price'), part_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Selling price updated"})


# ============================================================
# DELIVERIES (Supplier Supply Events)
# ============================================================

@app.route('/deliveries', methods=['GET'])
def get_deliveries():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT delivery_id, supplier_id, supplier_name, part_id, part_name,
               qty, unit_price, total, part_type, part_condition, part_year,
               description, delivered_at
        FROM deliveries ORDER BY delivered_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    result = []
    for r in rows:
        result.append({
            "id":           r[0],
            "supplier_id":  r[1],
            "supplier_name":r[2],
            "part_id":      r[3],
            "part_name":    r[4],
            "qty":          r[5],
            "unit_price":   float(r[6]),
            "total":        float(r[7]),
            "type":         r[8] or "",
            "condition":    r[9] or "",
            "year":         r[10],
            "description":  r[11] or "",
            "datetime":     r[12].strftime("%Y-%m-%d %H:%M") if r[12] else ""
        })
    return jsonify(result)


@app.route('/add_delivery', methods=['POST'])
def add_delivery():
    d = request.get_json()
    cur = mysql.connection.cursor()

    # Insert delivery record
    cur.execute("""
        INSERT INTO deliveries (supplier_id, supplier_name, part_id, part_name,
                                qty, unit_price, total, part_type, part_condition,
                                part_year, description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        d.get('supplier_id'),
        d.get('supplier_name', ''),
        d.get('part_id') or None,
        d.get('part_name', ''),
        d.get('qty', 0),
        d.get('unit_price', 0),
        d.get('total', 0),
        d.get('type', ''),
        d.get('condition', 'New'),
        d.get('year') or None,
        d.get('description', '')
    ))

    # If linked to existing part, increment its stock
    if d.get('part_id'):
        cur.execute("UPDATE parts SET qty = qty + %s WHERE part_id = %s",
                    (d.get('qty', 0), d.get('part_id')))
    else:
        # New part — add it to inventory
        cur.execute("""
            INSERT INTO parts (name, type, condition_type, year, description,
                               supplier_price, selling_price, qty, supplier_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            d.get('part_name', ''),
            d.get('type', ''),
            d.get('condition', 'New'),
            d.get('year') or None,
            d.get('description', ''),
            d.get('unit_price', 0),
            0,
            d.get('qty', 0),
            d.get('supplier_name', '')
        ))

    # Notify manager
    cur.execute("""
        INSERT INTO notifications (recipient, recipient_id, message, notif_type, delivery_id)
        VALUES ('manager', 1, %s, 'delivery', LAST_INSERT_ID())
    """, (f"New delivery: {d.get('qty')}x {d.get('part_name')} from {d.get('supplier_name')}",))

    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Delivery recorded successfully"})


# ============================================================
# SALES
# ============================================================

@app.route('/sales', methods=['GET'])
def get_sales():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT s.sale_id, s.receipt_code, s.customer_name, s.pay_method,
               s.total_amount, s.sold_at,
               sa.full_name AS sa_name
        FROM sales s
        LEFT JOIN sales_assistants sa ON s.sa_id = sa.sa_id
        ORDER BY s.sold_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    result = []
    for r in rows:
        result.append({
            "id":            r[0],
            "receipt_code":  r[1],
            "customer_name": r[2],
            "pay_method":    r[3],
            "total":         float(r[4]),
            "sold_at":       r[5].strftime("%Y-%m-%d %H:%M") if r[5] else "",
            "sa_name":       r[6] or "Unknown"
        })
    return jsonify(result)


@app.route('/add_sale', methods=['POST'])
def add_sale():
    d = request.get_json()
    items = d.get('items', [])
    if not items:
        return jsonify({"error": "No items in sale"}), 400

    receipt_code = "RCP-" + str(uuid.uuid4())[:8].upper()
    total_amount = sum(i['qty'] * i['unit_price'] for i in items)

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO sales (receipt_code, sa_id, customer_name, pay_method, total_amount)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        receipt_code,
        d.get('sa_id'),
        d.get('customer_name', 'Walk-in'),
        d.get('pay_method', 'cash'),
        total_amount
    ))
    sale_id = cur.lastrowid

    for item in items:
        cur.execute("""
            INSERT INTO sale_items (sale_id, part_id, part_name, qty, unit_price, line_total)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            sale_id,
            item.get('part_id'),
            item.get('part_name', ''),
            item.get('qty'),
            item.get('unit_price'),
            item.get('qty') * item.get('unit_price')
        ))
        # Stock is deducted automatically by the DB trigger trg_sale_item_deduct_stock

    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Sale recorded", "receipt_code": receipt_code, "total": total_amount})


@app.route('/sale_items/<int:sale_id>', methods=['GET'])
def get_sale_items(sale_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT item_id, part_id, part_name, qty, unit_price, line_total
        FROM sale_items WHERE sale_id = %s
    """, (sale_id,))
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "item_id":    r[0],
        "part_id":    r[1],
        "part_name":  r[2],
        "qty":        r[3],
        "unit_price": float(r[4]),
        "line_total": float(r[5])
    } for r in rows])


# ============================================================
# MANAGERS
# ============================================================

@app.route('/register_manager', methods=['POST'])
def register_manager():
    d = request.get_json()
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO managers (full_name, username, email, password_hash)
            VALUES (%s, %s, %s, %s)
        """, (
            d.get('full_name'),
            d.get('username'),
            d.get('email', ''),
            hash_password(d.get('password', ''))
        ))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Manager registered"})
    except Exception as e:
        cur.close()
        return jsonify({"error": str(e)}), 400


# ============================================================
# SUPPLIERS
# ============================================================

@app.route('/suppliers', methods=['GET'])
def get_suppliers():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT supplier_id, full_name, username, company, phone, email,
               parts_offered, status, registered_at
        FROM suppliers ORDER BY registered_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "id":            r[0],
        "full_name":     r[1],
        "username":      r[2],
        "company":       r[3] or "",
        "phone":         r[4] or "",
        "email":         r[5] or "",
        "parts_offered": r[6] or "",
        "status":        r[7],
        "registered_at": r[8].strftime("%Y-%m-%d %H:%M") if r[8] else ""
    } for r in rows])


@app.route('/register_supplier', methods=['POST'])
def register_supplier():
    d = request.get_json()
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO suppliers (full_name, username, company, phone, email,
                                   parts_offered, password_hash, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            d.get('full_name'),
            d.get('username'),
            d.get('company', ''),
            d.get('phone', ''),
            d.get('email', ''),
            d.get('parts_offered', ''),
            hash_password(d.get('password', ''))
        ))
        mysql.connection.commit()

        # Notify manager of new supplier registration
        cur.execute("""
            INSERT INTO notifications (recipient, recipient_id, message, notif_type)
            VALUES ('manager', 1, %s, 'supplier_reg')
        """, (f"New supplier registration: {d.get('full_name')} ({d.get('company', '')})",))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Supplier registered, awaiting approval"})
    except Exception as e:
        cur.close()
        return jsonify({"error": str(e)}), 400


@app.route('/approve_supplier/<string:supplier_id>', methods=['PUT'])
@app.route('/approve_supplier/<string:supplier_id>', methods=['PUT'])
def approve_supplier(supplier_id):
    d = request.get_json()
    status = d.get('status', 'approved')
    username = d.get('username', '')   # <-- pass username as fallback lookup
    cur = mysql.connection.cursor()

    # Try to find by username (since frontend uses generated string IDs)
    cur.execute("SELECT supplier_id FROM suppliers WHERE username = %s", (username,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"error": "Supplier not found"}), 404

    db_id = row[0]
    cur.execute("UPDATE suppliers SET status = %s WHERE supplier_id = %s", (status, db_id))
    cur.execute("""
        INSERT INTO notifications (recipient, recipient_id, message, notif_type)
        VALUES ('supplier', %s, %s, 'approval')
    """, (db_id, f"Your account has been {status}."))

    mysql.connection.commit()
    cur.close()
    return jsonify({"message": f"Supplier {status}"})


# ============================================================
# SALES ASSISTANTS
# ============================================================

@app.route('/sales_assistants', methods=['GET'])
def get_sales_assistants():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT sa_id, full_name, username, email, counter_name, registered_at, is_active
        FROM sales_assistants ORDER BY registered_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "id":            r[0],
        "full_name":     r[1],
        "username":      r[2],
        "email":         r[3] or "",
        "counter_name":  r[4],
        "registered_at": r[5].strftime("%Y-%m-%d %H:%M") if r[5] else "",
        "is_active":     bool(r[6])
    } for r in rows])


@app.route('/register_sa', methods=['POST'])
def register_sa():
    d = request.get_json()
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO sales_assistants (full_name, username, email, password_hash, counter_name)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            d.get('full_name'),
            d.get('username'),
            d.get('email', ''),
            hash_password(d.get('password', '')),
            d.get('counter_name', 'Counter 1')
        ))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Sales assistant registered"})
    except Exception as e:
        cur.close()
        return jsonify({"error": str(e)}), 400


@app.route('/toggle_sa/<int:sa_id>', methods=['PUT'])
def toggle_sa(sa_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE sales_assistants SET is_active = NOT is_active WHERE sa_id = %s", (sa_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Sales assistant status toggled"})


# ============================================================
# LOGIN (all roles)
# ============================================================

@app.route('/login', methods=['POST'])
def login():
    d = request.get_json()
    username = d.get('username', '')
    password = hash_password(d.get('password', ''))

    cur = mysql.connection.cursor()

    # Check manager
    cur.execute("SELECT manager_id, full_name FROM managers WHERE username=%s AND password_hash=%s",
                (username, password))
    row = cur.fetchone()
    if row:
        cur.close()
        return jsonify({"role": "manager", "id": row[0], "name": row[1]})

    # Check supplier (must be approved)
    cur.execute("""SELECT supplier_id, full_name, status FROM suppliers
                   WHERE username=%s AND password_hash=%s""", (username, password))
    row = cur.fetchone()
    if row:
        cur.close()
        if row[2] != 'approved':
            return jsonify({"error": f"Account is {row[2]}"}), 403
        return jsonify({"role": "supplier", "id": row[0], "name": row[1]})

    # Check sales assistant (must be active)
    cur.execute("""SELECT sa_id, full_name, counter_name, is_active FROM sales_assistants
                   WHERE username=%s AND password_hash=%s""", (username, password))
    row = cur.fetchone()
    cur.close()
    if row:
        if not row[3]:
            return jsonify({"error": "Account is deactivated"}), 403
        return jsonify({"role": "sa", "id": row[0], "name": row[1], "counter": row[2]})

    return jsonify({"error": "Invalid username or password"}), 401


# ============================================================
# MESSAGES (Manager <-> Supplier chat)
# ============================================================

@app.route('/messages/<int:supplier_id>', methods=['GET'])
def get_messages(supplier_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT message_id, sender_role, sender_id, body, sent_at
        FROM messages
        WHERE (sender_role='manager' AND recipient_id=%s)
           OR (sender_role='supplier' AND sender_id=%s)
        ORDER BY sent_at ASC
    """, (supplier_id, supplier_id))
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "id":          r[0],
        "sender_role": r[1],
        "sender_id":   r[2],
        "body":        r[3],
        "sent_at":     r[4].strftime("%Y-%m-%d %H:%M") if r[4] else ""
    } for r in rows])


@app.route('/send_message', methods=['POST'])
def send_message():
    d = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO messages (sender_role, sender_id, recipient_id, body)
        VALUES (%s, %s, %s, %s)
    """, (
        d.get('sender_role'),
        d.get('sender_id'),
        d.get('recipient_id'),
        d.get('body', '')
    ))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Message sent"})


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route('/notifications/<string:role>/<int:recipient_id>', methods=['GET'])
def get_notifications(role, recipient_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT notif_id, message, notif_type, is_read, created_at
        FROM notifications
        WHERE recipient=%s AND recipient_id=%s
        ORDER BY created_at DESC
    """, (role, recipient_id))
    rows = cur.fetchall()
    cur.close()
    return jsonify([{
        "id":         r[0],
        "message":    r[1],
        "type":       r[2] or "",
        "is_read":    bool(r[3]),
        "created_at": r[4].strftime("%Y-%m-%d %H:%M") if r[4] else ""
    } for r in rows])


@app.route('/mark_read/<int:notif_id>', methods=['PUT'])
def mark_read(notif_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE notifications SET is_read = TRUE WHERE notif_id = %s", (notif_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Notification marked as read"})


# ============================================================
# STOCK UPDATES (SA corrections)
# ============================================================

@app.route('/update_stock', methods=['POST'])
def update_stock():
    d = request.get_json()
    part_id  = d.get('part_id')
    new_qty  = d.get('new_qty')

    cur = mysql.connection.cursor()
    cur.execute("SELECT qty, name FROM parts WHERE part_id = %s", (part_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"error": "Part not found"}), 404

    old_qty = row[0]
    cur.execute("UPDATE parts SET qty = %s WHERE part_id = %s", (new_qty, part_id))
    cur.execute("""
        INSERT INTO stock_updates (sa_id, part_id, part_name, old_qty, new_qty, note)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        d.get('sa_id'),
        part_id,
        row[1],
        old_qty,
        new_qty,
        d.get('note', '')
    ))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Stock updated"})


# ============================================================
# SA SESSIONS (login/logout tracking)
# ============================================================

@app.route('/sa_login_session', methods=['POST'])
def sa_login_session():
    d = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO sa_sessions (sa_id, counter_name) VALUES (%s, %s)
    """, (d.get('sa_id'), d.get('counter_name', 'Counter 1')))
    mysql.connection.commit()
    session_id = cur.lastrowid
    cur.close()
    return jsonify({"message": "Session started", "session_id": session_id})


@app.route('/sa_logout_session/<int:session_id>', methods=['PUT'])
def sa_logout_session(session_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE sa_sessions SET logout_at = NOW() WHERE session_id = %s", (session_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"message": "Session ended"})


# ============================================================
# REPORTS / DASHBOARD STATS
# ============================================================

@app.route('/dashboard_stats', methods=['GET'])
def dashboard_stats():
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM parts")
    total_parts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM parts WHERE qty = 0")
    out_of_stock = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM parts WHERE qty > 0 AND qty < 5")
    low_stock = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE DATE(sold_at) = CURDATE()")
    sales_today = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM suppliers WHERE status = 'pending'")
    pending_suppliers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM sales WHERE DATE(sold_at) = CURDATE()")
    transactions_today = cur.fetchone()[0]

    cur.close()
    return jsonify({
        "total_parts":        total_parts,
        "out_of_stock":       out_of_stock,
        "low_stock":          low_stock,
        "sales_today":        float(sales_today),
        "pending_suppliers":  pending_suppliers,
        "transactions_today": transactions_today
    })


# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    app.run(debug=True)
