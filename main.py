from flask import Flask, request, render_template,send_file, jsonify, make_response
from datetime import datetime
from fuzzywuzzy import fuzz, process
import requests
import json
import random
import csv
import io
import os
from flask_cors import CORS

#local libraries
from database import Database
from file_control import File_Control
from collector import Collector

database=Database()
# collections=Euclid()

app = Flask(__name__)
CORS(app)




#--------------------------------------------------------------------------------------------------------------
#AUTH AND ACCOUNT

# Pinging the system
@app.route('/ping', methods=['GET'])
def ping():
    return {'status': 'running'}

# Login to account
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    log = database.login(email, password)
    return log

#Editor login to account
@app.route('/editorlogin', methods=['POST'])
def editor_login():
  data = request.get_json()
  email=data.get('email')
  password=data.get('password')
  log=database.login(email,password)
  return log

# Admin login to account
@app.route('/adminlogin', methods=['POST'])
def admin_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    key = data.get('key')
    if key == "0000admincenter0000":
        log = database.adminlogin(email, password)
        return log
    else:
        return {'status': 'Account not authorized to be admin'}

# Register a new account
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    user_type = data.get('user_type')
    code = data.get('code')
    password = data.get('password')
    phone = data.get('phone')
    lawfirm_name="individual"
    isadmin='false'
    if user_type=="org":
        lawfirm_name = data.get('lawfirm_name')
        isadmin='true'
    add = database.add_user(name, email, phone, user_type, code, lawfirm_name, password, isadmin)
    return add
