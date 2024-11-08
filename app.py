import json
import os
from flask import Flask, jsonify, request
from tinydb import TinyDB, Query

app = Flask(__name__)

# Initialize TinyDB and create tables for carts and employees
db = TinyDB('database.json')
carts_table = db.table('carts')
employees_table = db.table('employees')

active_sessions = {}

@app.route('/employees', methods=['GET'])
def get_employees():
    """Retrieve a list of all employees."""
    employees = employees_table.all()
    return jsonify({"employees": employees})

@app.route('/carts', methods=['GET'])
def get_carts():
    """Retrieve a list of all carts."""
    carts = carts_table.all()
    return jsonify({"carts": carts})

@app.route('/authenticate', methods=['POST'])
def handle_authenticate():
    """
    Handle login/logout actions based on RFID and cart UUID.
    Expected JSON payload: { "rfid": <employee_rfid>, "action": "login" or "logout", "cart_uuid": <cart_uuid> }
    """
    data = request.get_json()
    rfid = data.get("rfid")
    action = data.get("action")
    cart_uuid = data.get("cart")

    # Find employee by RFID
    employee = employees_table.get(Query().rfid == str(rfid))

    if not employee:
        return jsonify({"error": "RFID not recognized"}), 404

    # Handle login action
    if action == "login":
        if employee["position"] not in ["janitor", "mike"]:
            return jsonify({"error": "Unauthorized position for cart usage"}), 403

        # Check if the employee is already logged in
        if rfid in active_sessions:
            return jsonify({"error": "Employee already logged in"}), 400

        # Find the cart by UUID
        cart = carts_table.get(Query().rfid == str(cart_uuid))

        if not cart:
            return jsonify({"error": "Cart not found"}), 404

        # If cart is available (not assigned to anyone yet)
        if cart.get("assigned_to") is None:
            # Assign cart to the employee
            carts_table.update({"assigned_to": rfid}, Query().rfid == cart_uuid)
            active_sessions[rfid] = {"employee": employee, "cart_id": cart["id"]}
            return jsonify({
                "message": f"{employee['name']} ({employee['position']}) logged in successfully. Assigned to Cart {cart['id']}"
            }), 200
        else:
            return jsonify({"error": "Cart is already assigned"}), 400

    # Handle logout action
    elif action == "logout":
        if rfid in active_sessions:
            # Get the assigned cart UUID
            cart_id = active_sessions[rfid]["cart_id"]
            # Release the cart by setting assigned_to to None
            carts_table.update({"assigned_to": None}, Query().id == cart_id)
            # Remove the employee from active sessions
            del active_sessions[rfid]

            return jsonify({
                "message": f"{employee['name']} ({employee['position']}) logged out successfully. Cart {cart_id} is now available"
            }), 200
        else:
            return jsonify({"error": "Employee is not logged in"}), 400

    # Invalid action
    return jsonify({"error": "Invalid action"}), 400

def load_json_data(path: str) -> list[dict]:
    """Load data from a JSON file."""
    with open(path, 'r') as f:
        return json.load(f)

def main():
    """Load data from JSON files into TinyDB and start the app."""
    data_path = "./data"
    employees = load_json_data(os.path.join(data_path, 'employees.json'))
    carts = load_json_data(os.path.join(data_path, 'carts.json'))

    # Insert data into TinyDB (only if tables are empty)
    if len(employees_table) == 0:
        employees_table.insert_multiple(employees)
    if len(carts_table) == 0:
        carts_table.insert_multiple(carts)

    app.run(debug=True)

if __name__ == '__main__':
    main()
