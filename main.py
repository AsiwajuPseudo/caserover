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
from process import Process
from euclid import Euclid
from graph import Graph
from tools import Tools
from file import File
from temp_file import create_dir,delete_dir, generate_tree, get_dir,process_path,move_files, deli_file, search_file

database=Database()
collections=Euclid()

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
    atype = data.get('type')
    code = data.get('code')
    password = data.get('password')
    phone = data.get('phone')
    add = database.add_user(name, email, phone, atype, code, password)
    return add