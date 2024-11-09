import json
import os#

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from tinydb import TinyDB, Query

app = Flask(__name__)

import time
db = TinyDB('database.json')
carts_table = db.table('carts')
employees_table = db.table('employees')
lost_mops_table = db.table('lost_mops')

active_sessions = {}

def api_response(message: str, code: int, body: dict = {}) -> tuple[Response, int]:
    print(f"[{code}]: {message}")
    if code != 200:
        response = {'error': message}
    else:
        response = {'message': message}
    response |= body
    return jsonify(response), code


@app.route('/employees', methods=['GET'])
def get_employees():
    employees = employees_table.all()
    return jsonify({"employees": employees}), 200

@app.route('/carts', methods=['GET'])
def get_carts():
    carts = carts_table.all()
    return jsonify({"carts": carts}), 200


@app.route('/lost_mops', methods=['GET'])
def get_lost_table():
    lost_mops = lost_mops_table.all()
    return jsonify({"lost_mops": lost_mops}), 200

@app.route('/sensor', methods=['POST'])
def handle_sensor():
    data = request.get_json()
    cart_uuid = data.get("cart")
    _ = data.get("action")
    cart = carts_table.get(Query().uuid == str(cart_uuid))
    if not cart:
        return api_response("Cart not found", 404)

    assigned_to = cart.get("assigned_to", None)

    if assigned_to is None:
        return api_response(f"Cart {cart_uuid} is not in use", 403)

    employee = employees_table.get(Query().rfid == assigned_to)

    if employee['position'] != 'janitor':
        return api_response("Employee is not a janitor", 403)

    dirty_cloths = cart['dirty_cloths'] + 1
    carts_table.update({"dirty_cloths": dirty_cloths}, Query().uuid == cart_uuid)

    print(f"There are now {dirty_cloths} dirty cloths/mops in the cart {cart_uuid}")

    return api_response(f"{employee['name']} {employee['surname']} has placed 1 item in the dirty bin of cart {cart_uuid}", 200)


@app.route('/authenticate', methods=['POST'])
def handle_authenticate():
    data = request.get_json()
    rfid = data.get("rfid")
    action = data.get("action")
    cart_uuid = data.get("cart")

    employee = employees_table.get(Query().rfid == str(rfid))

    if not employee:
        return api_response("RFID not recognized", 404)

    if action == "login":
        if employee["position"] not in ["janitor", "mike"]:
            return api_response("Unauthorized position for cart usage", 403)

        if rfid in active_sessions:
            return api_response("Employee already logged in", 400)

        cart = carts_table.get(Query().uuid == str(cart_uuid))

        if not cart:
            return api_response("Cart not found", 404)

        if cart.get("assigned_to") is None:
            carts_table.update({"assigned_to": rfid}, Query().uuid == cart_uuid)
            active_sessions[rfid] = {"employee": employee, "cart_id": cart["uuid"]}
            return api_response(f"{employee['name']} {employee['surname']} ({employee['position']}) logged in successfully. Assigned to Cart {cart['uuid']}", 200, body={"position": employee["position"]})
        else:
            return api_response("Cart is already assigned", 400)

    elif action == "logout":
        if rfid in active_sessions:

            cart_id = active_sessions[rfid]["cart_id"]

            cart = carts_table.get(Query().uuid == cart_id)

            lost_mops = cart['clean_cloths'] - cart['dirty_cloths']

            if lost_mops > 0:
                lost_mops_table.insert({"cart": cart_id, "employee": employee['rfid'], "lost_mops": lost_mops})
                print(f"{employee['name']} {employee['surname']} lost {lost_mops} mops")

            carts_table.update({"assigned_to": None}, Query().uuid == cart_id)
            del active_sessions[rfid]

            return api_response(f"{employee['name']} {employee['surname']} ({employee['position']}) logged out successfully. Cart {cart_id} is now available", 200, body={"position": employee["position"]})
        else:
            return api_response("Employee is not logged in", 400)

    return api_response("Invalid action", 400)

def load_json_data(path: str) -> list[dict]:
    with open(path, 'r') as f:
        return json.load(f)

def main():
    data_path = "./data"
    employees = load_json_data(os.path.join(data_path, 'employees.json'))
    carts = load_json_data(os.path.join(data_path, 'carts.json'))

    if len(employees_table) == 0:
        employees_table.insert_multiple(employees)
    if len(carts_table) == 0:
        carts_table.insert_multiple(carts)

    app.run(host="0.0.0.0", debug=True)
    CORS(app, origins=["0.0.0.0"])

if __name__ == '__main__':
    main()
