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
# AUTH AND ACCOUNT MANAGEMENT

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

# Superuser login to account
@app.route('/superuserlogin', methods=['POST'])
def superuser_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    result = database.superuser_login(email, password)
    return result

# Add new superuser
@app.route('/add_superuser', methods=['POST'])
def add_superuser():
    data = request.get_json()
    admin_id = data.get('admin_id')
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    result = database.add_superuser(admin_id, name, email, password)
    return result

# Change superuser password
@app.route('/change_superuser_password', methods=['POST'])
def change_superuser_password():
    data = request.get_json()
    admin_id = data.get('admin_id')
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    result = database.change_superuser_password(admin_id, old_password, new_password)
    return result

# Get all superusers
@app.route('/get_superusers', methods=['GET'])
def get_superusers():
    admin_id = request.args.get('admin_id')
    result = database.get_superusers(admin_id)
    return result

# Delete a superuser
@app.route('/delete_superuser', methods=['POST'])
def delete_superuser():
    data = request.get_json()
    admin_id = data.get('admin_id')
    admin_id_to_delete_id = data.get('admin_id_to_delete')
    result = database.delete_superuser(admin_id, admin_id_to_delete_id)
    return result

# Register a new account
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    user_type = data.get('user_type')
    code = "00000"
    password = data.get('password')
    phone = data.get('phone')
    lawfirm_name="individual"
    isadmin = 'false'
    if user_type=="org":
        lawfirm_name = data.get('lawfirm_name')
        isadmin ='true'
    result = database.add_user(name, email, phone, user_type, code, lawfirm_name, password, isadmin)
    return result


# Change Password
@app.route('/password', methods=['POST'])
def change_password():
  data = request.get_json()
  old_password = data.get('old_password')
  new_password = data.get('new_password')
  user_id = data.get('user_id')
  passwd = database.change_password(user_id, old_password, new_password)
  return passwd

#view user profile
@app.route('/user_profile', methods=['GET'])
def view_user_profile():
  user_id = request.args.get('user_id')
  profile = database.user_profile(user_id)
  return profile

#view all users profile
@app.route('/allusers', methods=['GET'])
def view_all_profiles():
  users = database.profiles()
  return {'users': users}

# Subscribe a user
@app.route('/subscribe_user', methods=['POST'])
def subscribe_user():
  data = request.get_json()
  user_id=data.get('user_id')
  next_date=data.get('next_date')
  update=database.subscribe_user(user_id,next_date)
  users=database.profiles()
  return {'status':update,'users':users}

# Subscribe an organisation
@app.route('/subscribe_org', methods=['POST'])
def subscribe_orginisation():
  data = request.get_json()
  code = data.get('code')
  next_date=data.get('next_date')
  update=database.subscribe_org(code,next_date)
  users=database.profiles()
  return {'status': update,'users':users}

# Delete a user profile
@app.route('/delete_user', methods=['GET'])
def delete_profile():
  user_id=request.args.get('user_id')
  op = database.delete_user(user_id)
  users=database.profiles()
  return {'status': op, 'users':users}

#---------------------------------------------------------------------------------------------------------------

# ADMIN USER MANAGEMENT

# Admin adds a new user to their lawfirm
@app.route('/admin_add_user', methods=['POST'])
def admin_add_user():
    data = request.get_json()
    admin_id = data.get('admin_id')
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    result = database.admin_add_user(admin_id, name, email, phone, password)
    
    if result.get('status') == 'success':
        # Get updated list of users in the organization
        org_users = database.get_org_users(admin_id)
        return {'status': 'success', 'user': result.get('user'), 'org_users': org_users.get('users',[])}
    else:
        return result
    
# Admin deletes a user from their lawfirm
@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    data = request.get_json()
    admin_id = data.get('admin_id')
    user_id_to_delete = data.get('user_id')
    
    delete = database.admin_delete_user(admin_id, user_id_to_delete)
    if delete.get('status') == 'success':
        # Get updated list of users in the organization
        org_users = database.get_org_users(admin_id)
        return {'status': 'success', 'org_users': org_users.get('users',[])}
    else:
        return delete
    
# Admin views all users in their lawfirm
@app.route('/org_users', methods=['GET'])
def get_org_users():
    admin_id = request.args.get('admin_id')
    result = database.get_org_users(admin_id)
    return result
    
# Admin updates a user's status in their lawfirm
@app.route('/admin/update_user_status', methods=['POST'])
def admin_update_user_status():
    data = request.get_json()
    admin_id = data.get('admin_id')
    user_id = data.get('user_id')
    new_status = data.get('status')
    
    update = database.admin_update_user_status(admin_id, user_id, new_status)
    
    if update.get('status') == 'success':
        # Get updated list of users in the organization
        org_users = database.get_org_users(admin_id)
        return {'status': 'success', 'org_users': org_users.get('users',[])}
    else:
        return update

#------------
if __name__=='__main__':
    app.run(host='0.0.0.0',port='8080')

