from flask import Flask, request, render_template,send_file, jsonify, make_response
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz, process
import requests
import json
import random
import csv
import io
import os
from flask_cors import CORS
import jwt
import functools
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging


load_dotenv()

#local libraries
from database import Database
from file_control import File_Control
from collector import Collector
from process import Process
from euclid import Euclid
from graph import Graph
from tools import Tools

database=Database()
collections=Euclid()

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)

# Security configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY') # Get from environment variable
JWT_EXPIRATION_DELTA = timedelta (days = 30)
UPLOAD_FOLDER = '../files/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'htm', 'html', 'csv'}

# Setup rate limiting to prevent brute force attacks.
limiter = Limiter(
  app=app,
  key_func=get_remote_address,
  default_limits=["200  per day", "50 per hour"]
)

#----------------------------------------------------------------------------------------------------------------
# AUTHENTICATION HELPERS

def generate_token(user_id, role='user'):
  ''''Generate a JWT token for authenticated user'''
  
  if not user_id:
    app.logger.error("generate_token() called with None user_id")
    return None
  payload = {
    'user_id': user_id,
    'role': role,
    'exp': datetime.utcnow() + JWT_EXPIRATION_DELTA,
    'iat': datetime.utcnow()   
  }
  app.logger.debug("Generated JWT Payload: %s", payload)
  return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

def token_required(f):
  '''Decorator for endpoints that require authentication'''
  @functools.wraps(f)
  def decorated(*args, **kwargs):
    token = request.cookies.get('auth_token') # Read token frim HTTP-only cookie
      
    if not token:
      return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
    
    try:
      # Decode and verify the token
      data = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
      current_user = data['user_id']
      app.logger.debug("Decoded JWT Data: %s", data)
      
      # Add user info to kwargs so the route function can access it
      kwargs['current_user_id'] = current_user
      kwargs['user_role'] = data.get('role', 'user')
      
    except jwt.ExpiredSignatureError:
      return jsonify({'error': 'Authentication token has expired', 'code': 'TOKEN_EXPIRED' }), 401
    except jwt.InvalidTokenError:
      return jsonify({'error': 'Invalid authentication token', 'code': 'INVALID_TOKEN'}), 401
    
    return f(*args, **kwargs)
  return decorated

def admin_required(f):
  '''Decorator for endpoints that require admin privileges'''
  @functools.wraps(f)
  @token_required
  def decorated(*args, **kwargs):
    user_role = kwargs.get('user_role')
    
    if user_role != 'admin' and user_role != 'superuser':
      return jsonify({'error': 'Admin privileges required', 'code': 'ADMIN_REQUIRED'}), 403
    
    return f(*args, **kwargs)
  return decorated

def superuser_required(f):
  '''Decorator for endpoints that require superuser privileges'''
  @functools.wraps(f)
  @token_required
  def decorated(*args, **kwargs):
    user_role = kwargs.get('user_role')
    
    if user_role != 'superuser':
      return jsonify({'error': 'Superuser privileges required', 'code': 'SUPERUSER_REQUIRED'}), 403
    
    return f(*args, **kwargs)
  return decorated

#--------------------------------------------------------------------------------------------------------------
# AUTH AND ACCOUNT MANAGEMENT

# Pinging the system
@app.route('/ping', methods=['GET'])
def ping():
    return {'status': 'running'}

# Login to account
@app.route('/login', methods=['POST'])
@limiter.limit("10 per minute") # Rate limit to prevent brute force attacks
def login():
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
      return jsonify({'error': 'Missing email or password'}), 400
    
    log = database.login(email, password)
    
    if log.get('status') == 'success':
      # Generate JWT token
      user_id = log.get('user')
      role = 'admin' if log.get('isadmin') == 'true' else 'user'
      token = generate_token(user_id, role)
      
      # Set token as HTTP-only cookie
      response = jsonify({'status': 'success', 'user_id': user_id})
      # Set cookie domain to caserover.com
      # response.set_cookie('auth_token', token, domain='caserover.com', httponly=True, secure=True, samesite='Strict') # Change secure to True before deployment
      # return response
      
      response.set_cookie('auth_token', token, httponly=True, secure=True, samesite='Strict') # Change secure to True before deployment
      return response
    
    return log
  
@app.route('/logout', methods=['POST'])
@token_required
def logout(current_user_id, user_role):
  '''Logs user out by clearing the auth cookie'''
  response = jsonify({'status': 'success', 'message': 'Logged out'})
  response.set_cookie('auth_token', '', expires=0, httponly=True, secure=True, samesite='Strict' )
  return response

#Editor login to account
@app.route('/editorlogin', methods=['POST'])
@limiter.limit("10 per minute")
def editor_login():
  data = request.get_json()
  if not data:
    return jsonify({'error': 'No data provided'}), 400
  email=data.get('email')
  password=data.get('password')
  
  if not email or not password:
    return jsonify({'error': 'Missing email or password'}), 400
  
  log=database.login(email,password)
  
  if log.get('status') == 'success':
    # Generate JWT token
    user_id = log.get('user')
    role = 'editor'
    token = generate_token(user_id, role)
    
    log['token'] = token
  
  return log

# Superuser login to account
@app.route('/superuserlogin', methods=['POST'])
@limiter.limit("5 per minute")
def superuser_login():
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
      return jsonify({'error': 'Missing email or password'}), 400
    result = database.superuser_login(email, password)
    
    app.logger.debug(f"Superuser login response: {result}")
    
    if result.get('status') == 'success':
      # Generate JWT token with superuser role
      admin_id = result.get('admin')
      if not admin_id:
        app.logger.error("Superuser ID is missing from login response")
        return jsonify({'error': 'Login failed, no admin ID found'}), 500
      token = generate_token(admin_id, 'superuser')
      
     # Set token as HTTP-only cookie
      response = jsonify({'status': 'success'})
      response.set_cookie('auth_token', token, httponly=True, secure=True, samesite='Strict')
      return response
      
    return result

# Add new superuser (requires superuser privileges)
@app.route('/add_superuser', methods=['POST'])
@superuser_required
def add_superuser(current_user_id, user_role):
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    if not all([name, email, password]):
      return jsonify({'error': 'Missing required fields'}), 400
    
    # Now use the authenticated user ID instead of trusting the request
    admin_id = current_user_id
    
    result = database.add_superuser(admin_id, name, email, password)
    return result

# Change superuser password
@app.route('/change_superuser_password', methods=['POST'])
@superuser_required
def change_superuser_password(current_user_id, user_role):
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
      return jsonify({'error': 'Missing required fields'}), 400
    
    admin_id = current_user_id
    
    result = database.change_superuser_password(admin_id, old_password, new_password)
    return result

# Get all superusers (now requires superuser privileges)
@app.route('/get_superusers', methods=['GET'])
@superuser_required
def get_superusers(current_user_id, user_role):
    admin_id = current_user_id # Authenticated user ID
    result = database.get_superusers(admin_id)
    return result

# Delete a superuser
@app.route('/delete_superuser', methods=['DELETE'])
@superuser_required
def delete_superuser(current_user_id, user_role):
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    admin_id_to_delete = data.get('admin_id_to_delete')
    if not admin_id_to_delete:
      return jsonify({'error': 'Missing required fields'}), 400
    
    admin_id = current_user_id
    # Prevent self-deletion
    if admin_id == admin_id_to_delete:
      return jsonify({'error': 'Cannot delete your own superuser account'}), 400
    
    result = database.delete_superuser(admin_id, admin_id_to_delete)
    return result

# Register a new account
@app.route('/register', methods=['POST'])
@limiter.limit("5 per hour")
def register():
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name')
    email = data.get('email')
    user_type = data.get('user_type')
    code = "00000"
    password = data.get('password')
    phone = data.get('phone')
    if not all([name, email, password, user_type]):
      return jsonify({'error': 'Missing required fields'}), 400
    
    lawfirm_name="individual"
    isadmin = 'false'
    if user_type=="org":
        lawfirm_name = data.get('lawfirm_name')
        isadmin ='true'
    result = database.add_user(name, email, phone, user_type, code, lawfirm_name, password, isadmin)
    
    if result.get('status') == 'success':
      user_id = result.get('user')
      token = generate_token(user_id, 'admin' if isadmin == 'true' else 'user')
      
      response = jsonify({'status': 'success', 'user_id': user_id})
      response.set_cookie(
            'auth_token', token, httponly=True, secure=False, samesite='Strict'  # Secure=False for local testing
      )
      return response
    
    return result


# Change Password
@app.route('/password', methods=['POST'])
@token_required
def change_password(current_user_id, user_role):
  data = request.get_json()
  if not data:
    return jsonify({'error': 'No data provided'}), 400
  
  old_password = data.get('old_password')
  new_password = data.get('new_password')
  
  if not old_password or not new_password:
    return jsonify({'error': 'Missing required fields'}), 400
  
  user_id = current_user_id
  passwd = database.change_password(user_id, old_password, new_password)
  return passwd

#view user profile
@app.route('/user_profile', methods=['GET'])
@token_required
def view_user_profile(current_user_id, user_role):
    print(f"Fetching profile for user: {current_user_id}")
  # Admins can view other profiles by passing user_id in query
    requested_user_id = request.args.get('user_id', current_user_id)
  
  # Regular users can only view their own profile
    if user_role == 'user' and requested_user_id != current_user_id:
      return jsonify({'error': "Unauthorized to view other users' profile"}), 403

    profile = database.user_profile(requested_user_id)
    return profile

#view all users profile
@app.route('/allusers', methods=['GET'])
@superuser_required
def view_all_profiles(current_user_id, user_role):
    users = database.profiles()
    return {'status': 'success', 'users': users}

# Subscribe a user
@app.route('/subscribe_user', methods=['POST'])
@superuser_required # Require superuser privileges
def subscribe_user(current_user_id, user_role):
  data = request.get_json()
  if not data:
    return jsonify({'error': 'No data provided'}), 400
  user_id=data.get('user_id')
  next_date=data.get('next_date')
  
  if not user_id or not next_date:
    return jsonify({'error': 'Missing required fields'}), 400
  
  admin_id = current_user_id
  
  update=database.subscribe_user(admin_id, user_id, next_date)
  users=database.profiles()
  return {'status':update,'users':users}

# Subscribe an organisation
@app.route('/subscribe_org', methods=['POST'])
@superuser_required # Requires superuser privileges
def subscribe_orginisation(current_user_id, user_role):
  data = request.get_json()
  if not data:
    return jsonify({'error': 'No data provided'}), 400
  admin_id= current_user_id
  code = data.get('code')
  next_date=data.get('next_date')
  update=database.subscribe_org(admin_id, code,next_date)
  users=database.profiles()
  return {'status': update,'users':users}

# Delete a user profile
@app.route('/delete_user', methods=['DELETE'])
@admin_required
def delete_profile(current_user_id, user_role):
    user_id=request.args.get('user_id')
    if not user_id:
      return jsonify({'error': 'Missing user_id parameter'}), 400
  
    if user_id == current_user_id:
      return jsonify({'error': 'Cannot delete your own profile'}), 400
  
    op = database.delete_user(user_id)
    users=database.profiles()
    return {'status': op, 'users':users}

#---------------------------------------------------------------------------------------------------------------

# ADMIN USER MANAGEMENT

# Admin adds a new user to their lawfirm
@app.route('/admin_add_user', methods=['POST'])
@admin_required
def admin_add_user(current_user_id, user_role):
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    admin_id = current_user_id
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    if not all([name, email, password]):
      return jsonify({'error': 'Missing required fields'}), 400
    
    result = database.admin_add_user(admin_id, name, email, phone, password)
    
    if result.get('status') == 'success':
        # Get updated list of users in the organization
        org_users = database.get_org_users(admin_id)
        return {'status': 'success', 'user': result.get('user'), 'org_users': org_users.get('users',[])}
    else:
        return result
    
# Admin deletes a user from their lawfirm
@app.route('/admin_delete_user', methods=['DELETE'])
@admin_required
def admin_delete_user(current_user_id, user_role):
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    admin_id = current_user_id
    user_id_to_delete = data.get('user_id')
    
    if not user_id_to_delete:
      return jsonify({'error': 'Missing user id field'}), 400
    
    if admin_id == user_id_to_delete:
      return jsonify({'error': 'Cannot delete your own account'}), 400
    
    delete = database.admin_delete_user(admin_id, user_id_to_delete)
    if delete.get('status') == 'success':
        # Get updated list of users in the organization
        org_users = database.get_org_users(admin_id)
        return {'status': 'success', 'org_users': org_users.get('users',[])}
    else:
        return delete
    
# Admin views all users in their lawfirm
@app.route('/org_users', methods=['GET'])
@admin_required
def get_org_users(current_user_id, user_role):
    admin_id = current_user_id
    result = database.get_org_users(admin_id)
    results=[item for item in result['users'] if item['user_id']!=admin_id]
    return results
    
# Admin updates a user's status in their lawfirm
@app.route('/admin_update_user_status', methods=['PUT'])
@admin_required
def admin_update_user_status(current_user_id, user_role):
    data = request.get_json()
    if not data:
      return jsonify({'error': 'No data provided'}), 400
    
    admin_id = current_user_id
    
    user_id = data.get('user_id')
    new_status = data.get('status')
    
    if not user_id or new_status is None:
      return jsonify({'error': 'Missing required fields'}), 400
    
    update = database.admin_update_user_status(admin_id, user_id, new_status)
    
    if update.get('status') == 'success':
        # Get updated list of users in the organization
        org_users = database.get_org_users(admin_id)
        return {'status': 'success', 'org_users': org_users.get('users',[])}
    else:
        return update






#------------------------------------------CORE METHODS---------------------------


#add a chat
@app.route('/add_chat', methods=['POST'])
def add_chat():
  data = request.get_json()
  name=data.get('name')
  user=data.get('user_id')
  add=database.add_chat(user,name)
  chats=database.chats(user)
  return {"status":add,"chats":chats}

#delete a chat
@app.route('/deli_chat', methods=['GET'])
def deli_chat():
  chat=request.args.get('chat_id')
  user=request.args.get('user_id')
  deli=database.deli_chat(chat)
  chats=database.chats(user)

  return {"status":deli["status"],"chats":chats}

#retrieve all chats belonging to a user
@app.route('/chats', methods=['GET'])
def collect_chats():
  user=request.args.get('user_id')
  chats=database.chats(user)
  tables=collections.tables()
  table_data=[]
  tables_list=[]
  for col in tables:
    tables_list.append(col)

  return {"chats":chats,"tables":tables_list}

#retrieve all chats belonging to a user
@app.route('/messages', methods=['GET'])
def collect_messages():
  chat=request.args.get('chat_id')
  messages=database.messages(chat)

  return {"messages":messages}

#playground
@app.route('/play', methods=['POST'])
def run_playground():
  data = request.get_json()
  chat = data.get('chat_id')
  user = data.get('user_id')
  prompt = data.get('prompt')
  tool = data.get('tool')
  tools = Tools(collections)
  # Check if there is a valid chat or it's a new one
  if chat == '' or chat is None:
    name = tools.naming(prompt)
    add = database.add_chat(user, name)
    chat = add['chat']
  # Execute
  try:
    if tool == "assistant":
      history = database.messages(chat)
      answer, sources = tools.assistant(prompt, 4060, history)
    elif tool == "documents":
      # List all files from the directory
      history = database.messages(chat)
      files = os.listdir('../files/uploads/' + chat + '/')
      text = ""
      for file in files:
        t = File()
        data = {"document_name": file, "content": t.download('../files/uploads/' + chat + '/' + file)}
        text = text + str(data)
      # Check if there was a document
      if text == "":
        return "Please upload a document to be able to use this tool", []
      # Generate answer if document is available
      answer = tools.extracter(prompt, 4060, text, history)
      sources = files
    else:
      history = database.messages(chat)
      answer, sources = tools.rag(tool, prompt, history, 3, 4060)
  except Exception as e:
    print(e)
    p={"answer":[{"type":"paragraph","data":"Error generating content, please try again. If the error persist create a new workspace."}],"sources":[], "citations":[]}
    answer=json.dumps(p)
    sources=[]

  # Add answer to database
  add = database.add_message(chat, user, str(answer), prompt)
  messages = database.messages(chat)
  chats = database.chats(user)

  return {"messages": messages, "chats": chats, "current": chat}


#upload files for GPT
@app.route('/cloudupload', methods=['POST'])
def upload_files_gpt():
  chat = request.form.get('chat_id')
  transcript=[]
  files = request.files.getlist('files')
  if len(files) == 0:
    return {"status":"No file part"}
  # Create a temporary directory
  path="../files/uploads/"+chat+"/"
  folder=create_dir(path)
  if folder['message']=='error':
    return {"status":"Error creating folder"}
  # Save each file to the temporary directory
  for file in files:
    if file.filename == '':
      continue
    filename = os.path.join(path, file.filename)
    file.save(filename)
    name=file.filename
    '''
    if name.endswith('.pdf'):
      new_path="./files/pdf_images/"+chat+"/"
      folder=create_dir(new_path)
      t=File()
      t.pdf_to_images(name,path,new_path)
      vis=Vision()
      pages=vis.pdf_vision(name, new_path)
      print(pages)'''
  #upload files
  nodes=generate_tree(path)
  return {"status":"success",'nodes':nodes}

@app.route('/source', methods=['GET'])
def get_source():
  tool=request.args.get('tool')
  name=request.args.get('name')
  if tool=="assistant":
    return "Load html content"
  elif tool=="web":
    return {"url":name}
  elif tool=="documents":
    chat=request.args.get('chat_id')
    file="../files/uploads/"+chat+"/"+name
    return send_file(file, as_attachment=False)
  else:
    #search for the document
    file=search_file('../files/closed/'+tool+'/',name)
    if file:
      return send_file(file, as_attachment=False)
    else:
      return "File not found"


@app.route('/get_file', methods=['GET'])
def get_pdf():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  file_path='../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename
  if File_Control.check_path(file_path):
    return send_file(file_path, as_attachment=False)
  else:
    return jsonify({'error': 'Document does not exist'}), 400


#--------------------------------------------------EDITOR MODE METHODS




#Load all the tables currently created
@app.route('/tables', methods=['GET'])
def tables():
  #check if tables object exist
  if File_Control.check_path('../tables/') and File_Control.check_path('../tables/root.pkl'):
    tables=File_Control.open('../tables/root.pkl')
  else:
    #create folder
    File_Control.create_path('../tables/')
    tables=[]
    File_Control.save('../tables/root.pkl',tables)
    File_Control.save('../tables/files.pkl',tables)
  return {"tables":tables}

#create a table
@app.route('/add_table', methods=['POST'])
def create_table():
  data = request.get_json()
  name=data.get('name')
  type=data.get('type')
  #view what is in the tables
  tables=File_Control.open('../tables/root.pkl')
  vector=Euclid()
  add=vector.create_table(name)
  if add=='success':
    table_id=str(random.randint(1000,9999))
    table={"id":table_id,"name":name,"type":type,'count':0}
    tables.append(table)
    File_Control.save('../tables/root.pkl',tables)
    files=[]
    File_Control.save('../tables/'+name+'-'+table_id+'.pkl',files)
    File_Control.create_path('../temp/'+name+'-'+table_id+'/')
    File_Control.create_path('../data/'+name+'-'+table_id+'/')

    return {"result":"success","tables":tables}
  else:
    return {"result":"error creating vector database table, check table name","tables":tables}

#delete a table
@app.route('/delete_table', methods=['GET'])
def delete_table():
  table=request.args.get('id')
  name=request.args.get('name')
  tables=File_Control.open('../tables/root.pkl')
  vector=Euclid()
  dele=vector.delete_table(name)
  if dele=='success':
    files=File_Control.open('../tables/files.pkl')
    new_files=[item for item in files if item['table_id'] != table]
    new_tables=[item for item in tables if item['id'] != table]
    File_Control.save('../tables/root.pkl',new_tables)
    File_Control.save('../tables/files.pkl',new_files)
    File_Control.delete_file('../tables/'+name+'-'+table+'.pkl')
    tables=File_Control.open('../tables/root.pkl')
    File_Control.delete_path('../temp/'+name+'-'+table+'/')
    File_Control.delete_path('../data/'+name+'-'+table+'/')

    return {'tables':tables}
  else:
    return {'tables':tables}


#file upload
@app.route('/upload', methods=['POST'])
def upload_files():
  table_id = request.form.get('id')
  name = request.form.get('name')
  files = request.files.getlist('files')
  if len(files) == 0:
    return {'result':'zero'}
  path='../temp/'+name+'-'+table_id+'/'
  uploaded_files=[]
  n=0
  for file in files:
    if file.filename == '':
      continue
    file_id=str(random.randint(1000000000,9999999999))
    filename = os.path.join(path, file_id+'-'+file.filename)
    file.save(filename)
    uploaded_files.append({'filename':file.filename, 'file_id': file_id, 'table_id': table_id, 'table':name,'isProcessed':False})
    n=n+1

  other_files=File_Control.open('../tables/files.pkl')
  other_files.extend(uploaded_files)
  File_Control.save('../tables/files.pkl',other_files)
  tables=File_Control.open('../tables/root.pkl')
  table=next(item for item in tables if item['id'] == table_id)
  tables=[item for item in tables if item['id'] != table_id]
  table['count']=n
  tables.append(table)
  File_Control.save('../tables/root.pkl',tables)

  return {'result':'success','files':other_files}

#Load all unprocessed documents currently created
@app.route('/files', methods=['GET'])
def unproc_files():
  #check if files object exist
  tables=File_Control.open('../tables/root.pkl')
  if File_Control.check_path('../tables/files.pkl'):
    files=File_Control.open('../tables/files.pkl')
  else:
    #create folder
    File_Control.create_path('../tables/')
    files=[]
    File_Control.save('../tables/files.pkl',files)
  files=files[-100:]
  return {'files':files,'tables':tables}

#delete an unprocessed file
@app.route('/delete_unproc_file', methods=['GET'])
def delete_file_unprocessed():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  files=File_Control.open('../tables/files.pkl')
  if File_Control.check_path('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl'):
    file=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
    new_files=[item for item in files if item['file_id'] != file_id]
    vector=Euclid()
    deli=vector.delete(table,'file_id',file_id)
    if deli=='success':
      File_Control.save('../tables/files.pkl',new_files)
      File_Control.delete_file('../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename)
      File_Control.delete_file('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
      new_files=files[-100:]
      return {'files':new_files}
    else:
      files=files[-100:]
      return {'files':files}
  else:
    new_files=[item for item in files if item['file_id'] != file_id]
    File_Control.save('../tables/files.pkl',new_files)
    File_Control.delete_file('../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename)
    new_files=files[-100:]
    return {'files':new_files}

#delete a file
@app.route('/delete_file', methods=['GET'])
def delete_file():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  files=File_Control.open('../tables/files.pkl')
  file=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
  new_files=[item for item in files if item['file_id'] != file_id]
  vector=Euclid()
  deli=vector.delete(table,'file_id',file_id)
  cite=file['citation']
  graph=Graph()
  dele_graph=graph.delete_node(cite)
  if deli=='success' and dele_graph=='success':
    File_Control.save('../tables/files.pkl',new_files)
    File_Control.delete_file('../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename)
    File_Control.delete_file('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
    return {'files':new_files}
  else:
    return {'files':files}

#process a file
@app.route('/proc_file', methods=['GET'])
def proc_file():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  file_path='../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename
  collect=Collector()
  #process document using the AI
  proc=Process()
  tables=File_Control.open('../tables/root.pkl')
  tab=next(item for item in tables if item['id'] == table_id)
  if tab['type']=='ruling':
    if filename.lower().endswith('.pdf'):
      document=collect.pdf_raw(file_path)
    elif filename.lower().endswith('.docx'):
      document=collect.collect_docx(file_path)
    run=proc.court_proc(table, table_id, file_id, filename, document)
  elif tab['type']=='legislation':
    if filename.lower().endswith('.htm') or filename.lower().endswith('.html'):
      document=collect.html_styles(file_path)
      run=proc.legislation(table, table_id, file_id, filename, document)
    elif filename.lower().endswith('.pdf'):
      document=collect.pdf_raw(file_path)
      run=proc.legislation(table, table_id, file_id, filename, document)
    elif filename.lower().endswith('.docx'):
      document=collect.docx_styles(file_path)
      run=proc.legislation(table, table_id, file_id, filename, document)
  else:
    #other methods of processing documents
    run={'result':'method for processing does not exist','content':{}}
  #updated status
  files=File_Control.open('../tables/files.pkl')
  if run['result']=='success':
    #add to table
    File_Control.save('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl',run['content'])
    next(item for item in files if item['file_id'] == file_id)['isProcessed'] = True
    File_Control.save('../tables/files.pkl',files)

  else:
    print(run['result'])

  files=File_Control.open('../tables/files.pkl')
  files=files[-100:]
  return {'result':run['result'],'files':files}

#open a file
@app.route('/open_file', methods=['GET'])
def open_file():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  file=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
  tables=File_Control.open('../tables/root.pkl')
  tab=next(item for item in tables if item['id'] == table_id)
  cite=file['citation']
  graph=Graph()
  n=graph.search(cite)
  file_path='../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename
  collect=Collector()
  if filename.lower().endswith('.pdf'):
    document=collect.pdf_raw(file_path)
  elif filename.lower().endswith('.docx'):
    document=collect.docx_styles(file_path)
  elif filename.lower().endswith('.htm') or filename.lower().endswith('.html'):
    document=collect.html_styles(file_path)
  file['raw']=document
  file['sections']=[]
  #print(file)

  return {'file':file,'type':tab['type'],'graph':n}

#load all processed files
@app.route('/load_processed', methods=['GET'])
def load_all_processed_files():
  table1=request.args.get('table')
  #check if files object exist
  tables=File_Control.open('../tables/root.pkl')
  if File_Control.check_path('../tables/files.pkl'):
    files=File_Control.open('../tables/files.pkl')
  else:
    #create folder
    File_Control.create_path('../tables/')
    files=[]
    File_Control.save('../tables/files.pkl',files)

  processed_files=[]
  for file in files:
    if(file['isProcessed']==True):
      file_id=file['file_id']
      filename=file['filename']
      table_id=file['table_id']
      table=file['table']
      cont=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
      processed_files.append({'filename':filename, 'file_id': file_id, 'table_id': table_id, 'table':table, 'citation':cont['citation']})
  #load files from the provided table
  processed_files1=[item for item in processed_files if item['table']==table1]
  all_files=processed_files1[-20:]
  return {'files':all_files,'tables':tables}


#save a file for viewing later
@app.route('/save_file', methods=['POST'])
def save_file_as_bookmark():
  data = request.get_json()
  user_id=data.get('user_id')
  file_id=data.get('file_id')
  filename=data.get('filename')
  table_id=data.get('table_id')
  table=data.get('table')
  file=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
  tables=File_Control.open('../tables/root.pkl')
  tab=next(item for item in tables if item['id'] == table_id)
  cite=file['citation']
  save=database.save_doc(user_id, file_id, filename, table_id, table, cite)

  return save


#save a file for viewing later
@app.route('/load_saved_files', methods=['GET'])
def load_saved_files():
  user_id=request.args.get('user_id')
  saved=database.load_saved(user_id)

  return saved

#delete a file saved for viewing later
@app.route('/delete_saved_file', methods=['POST'])
def delete_saved_file():
  data = request.get_json()
  user_id=data.get('user_id')
  file_id=data.get('file_id')
  deli=database.deli_saved(user_id, file_id)

  return deli

#section processing
@app.route('/section_proc', methods=['GET'])
def process_section():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  section_number=request.args.get('section_number')
  file=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
  section=next(item for item in file['sections'] if item['section_number'] == section_number)
  proc=Process()
  run=proc.section_process(section)

  return {'section':run}

#section processing
@app.route('/regenerate', methods=['GET'])
def document_regenerate():
  file_id=request.args.get('file_id')
  filename=request.args.get('filename')
  table_id=request.args.get('table_id')
  table=request.args.get('table')
  file_path='../temp/'+table+'-'+table_id+'/'+file_id+'-'+filename
  collect=Collector()
  #process document using the AI
  proc=Process()
  document=collect.pdf_raw(file_path)
  run=proc.court_proc(table, table_id, file_id, filename, document)
  files=File_Control.open('../tables/files.pkl')
  vector=Euclid()
  deli=vector.delete(table,'file_id',file_id)
  if deli=='success':
    if run['result']=='success':
      #add to table
      File_Control.save('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl',run['content'])
      return {'result':run['result'],'file':run['content']}
    else:
      return {'result':'Error re-generating from the AI'}
  else:
    return {'result':'error deleting vector file'}

#upload changes to sections
@app.route('/upload_changes', methods=['POST'])
def upload_changes():
  data = request.get_json()
  file_id=data.get('file_id')
  filename=data.get('filename')
  table_id=data.get('table_id')
  table=data.get('table')
  document=data.get('document')
  vector=Euclid()
  deli=vector.delete(table,'file_id',file_id)
  if deli=='success':
    proc=Process()
    run=proc.update_legi(table, table_id, file_id, filename, document)
    if run=='success':
      File_Control.delete_file('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
      File_Control.save('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl',document)
      return {'result':'success'}
    else:
      return {'result':'Error embedding and adding to vector database'}
  else:
    return {'result':'Error deleting records from vector database'}

#do a raw search of the euclid database
@app.route('/raw_search', methods=['POST'])
def raw_search():
  data = request.get_json()
  table=data.get('table')
  query=data.get('query')
  vector=Euclid()
  r=vector.search(table,query,10)

  return {'documents':r}

#do a raw search of the euclid database
@app.route('/typing_search', methods=['GET'])
def typing_search():
  query=request.args.get('query')
  files=File_Control.open('../tables/files.pkl')
  processed_files=[]
  for file in files:
    if(file['isProcessed']==True):
      file_id=file['file_id']
      filename=file['filename']
      table_id=file['table_id']
      table=file['table']
      cont=File_Control.open('../data/'+table+'-'+table_id+'/'+file_id+'-'+filename+'.pkl')
      processed_files.append({'filename':filename, 'file_id': file_id, 'table_id': table_id, 'table':table, 'citation':cont['citation']})
  citations = [(file['citation'], file) for file in processed_files]
  matches = process.extract(query, [citation[0] for citation in citations], limit=20)
  matched_files=[]
  for file in matches:
    full=next(f for f in processed_files if f['citation']==file[0])
    matched_files.append(full)

  return jsonify({'documents':matched_files})

#deploy all documents into graph
@app.route('/deploy_graph', methods=['GET'])
def deploy_all_documents_to_graph():
  #check if files object exist
  tables=File_Control.open('../tables/root.pkl')
  files=File_Control.open('../tables/files.pkl')
  print('running deployment')
  documents=[]
  for file in files:
    type=next(item['type'] for item in tables if item['id'] == file['table_id'])
    file['type']=type
    documents.append(file)

  graph=Graph()
  n=graph.create_graph(documents)
  print('Done deploying')
  return {'result':'success'}

#deploy all documents into graph
@app.route('/show_graph', methods=['GET'])
def show_react_graph():
  graph=Graph()
  flow=graph.graph_data()
  return flow

#------------
if __name__=='__main__':
    app.run(host='0.0.0.0',port='8080')

