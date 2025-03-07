import sqlite3
import random
import json
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.db_path = 'datastore.db'
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                              (user_id TEXT, name TEXT, email TEXT, phone TEXT,user_type TEXT,code TEXT,lawfirm_name TEXT,status TEXT,next_date TEXT, password TEXT, isadmin TEXT, date_joined TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS models
                              (model_id TEXT,user_id TEXT,name TEXT,table_name TEXT,model TEXT,n INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS chats
                              (chat_id TEXT,user_id TEXT,name TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS messages
                              (chat_id TEXT,user_id TEXT,user TEXT,system TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS media
                              (chat_id TEXT,user_id TEXT,file TEXT,content TEXT)''')

        conn.commit()

    def add_user(self, name, email, phone,user_type,code, lawfirm_name, password, isadmin):
        user_id = "user" + str(random.randint(1000, 9999))
        status = "trial"
        if isadmin=="true":
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Generate a random code until a unique one is found
                while True:
                    new_code = random.randint(10000,99999)
                    cursor.execute("SELECT * FROM users WHERE code=?", (new_code,))
                    if not cursor.fetchone():
                        code=new_code
                        break
        current_datetime = datetime.now()
        date_joined = str(current_datetime.date())
        
        # Set billing date to 7 days from now
        next_billing_date = current_datetime + timedelta(days=7)
        next_date=str(next_billing_date.date())
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email=?", (email,))
                existing_user = cursor.fetchone()
                if existing_user:
                    return {"status": "Email already exists"}
                cursor.execute("INSERT INTO users (user_id, name, email, phone, user_type, code, lawfirm_name, status, next_date, password, isadmin, date_joined) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (user_id, name, email, phone,user_type, code, lawfirm_name, status, next_date, password, isadmin, date_joined))
                conn.commit()
                return {"status": "success","user":user_id}
        except Exception as e:
            return {"status": "Error: " + str(e)}
    
    def delete_user(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                conn.commit()
                return {"status":"success"}
        except Exception as e:
            return {"status":"Error: " + str(e)}
        
    # Admin register user using code
    def admin_add_user(self, admin_id, name, email, phone, password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the admin exists and has admin priviledges
                cursor.execute("SELECT * FROM users WHERE user_id=? AND isadmin='true'", (admin_id,))
                admin = cursor.fetchone()
                if not admin:
                    return {"status": "Unauthorized access!"}
                
                # Get admin's code and lawfirm name
                admin_code = admin[5]
                lawfirm_name = admin[6]

                # Check if the email already exists
                cursor.execute("SELECT * FROM users WHERE email=?", (email,))
                existing_user = cursor.fetchone()
                if existing_user:
                    return {"status": "Email already exists"}
                
                # Create a new user
                user_id = "user" + str(random.randint(1000, 9999))
                user_type = "org"
                isadmin = "false" # Regular user
                status = "trial"
                
                current_datetime = datetime.now()
                date_joined = str(current_datetime.date())
                
                # Set billing date same as admin
                next_billing_date = current_datetime + timedelta(days=7)
                next_date=str(next_billing_date.date())
                
                # Insert new user
                cursor.execute("INSERT INTO users (user_id, name, email, phone, user_type, code, lawfirm_name, status, next_date, password, isadmin, date_joined) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (user_id, name, email, phone, user_type, admin_code, lawfirm_name, status, next_date, password, isadmin, date_joined))
                conn.commit()
                return {"status": "success","user":user_id}
        except Exception as e:
            return {"status": "Error: " + str(e)}
 
    # Admin delete user
    def admin_delete_user(self, admin_id, user_id_to_delete):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the admin exists and has admin priviledges
                cursor.execute("SELECT * FROM users WHERE user_id=? AND isadmin='true'", (admin_id,))
                admin = cursor.fetchone()
                if not admin:
                    return {"status": "Unauthorized access!"}
                
                admin_code = admin[5]
                
                # Check if the user to be deleted exists and belongs to same organization
                cursor.execute("SELECT * FROM users WHERE user_id=? AND code=?", (user_id_to_delete, admin_code))
                user = cursor.fetchone()
                if not user:
                    return {"status": "User does not exist or does not belong to the same organization"}
                
                # Cannot delete admin user
                if admin_id == user_id_to_delete:
                    return {"status": "Cannot delete admin user"}
                
                # Delete the user
                cursor.execute("DELETE FROM users WHERE user_id=?", (user_id_to_delete,))
                conn.commit()
                return {"status": "success"}
        except Exception as e:
            return {"status": "Error: " + str(e)}
        
# Admin get users in orgamization (add date joined)
    def get_org_users(self, admin_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the admin exists and has admin priviledges
                cursor.execute("SELECT * FROM users WHERE user_id=? AND isadmin='true'", (admin_id,))
                admin = cursor.fetchone()
                if not admin:
                    return {"status": "Unauthorized access!"}
                
                # Get admin's code
                admin_code = admin[5]
                
                # Get all users in the same organization
                cursor.execute("SELECT * FROM users WHERE code=?", (admin_code,))
                org_users = cursor.fetchall()
                
                # Prepare response
                users_list = []
                for user in org_users:
                    user_data = {
                        "user_id": user[0],
                        "name": user[1],
                        "email": user[2],
                        "phone": user[3],
                        "user_type": user[4],
                        "code": user[5],
                        "lawfirm_name": user[6],
                        "status": user[7],
                        "next_date": user[8],
                        "isadmin": user[10],
                        "date_joined": user[11]
                    }
                    users_list.append(user_data)
                
                return {"status": "success", "users": users_list}
        except Exception as e:
            return {"status": "Error: " + str(e)}
        
    # Admin Update user status
    def update_user_status(self, admin_id, user_id_to_update, new_status):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the admin exists and has admin priviledges
                cursor.execute("SELECT * FROM users WHERE user_id=? AND isadmin='true'", (admin_id,))
                admin = cursor.fetchone()
                if not admin:
                    return {"status": "Unauthorized access!"}
                
                admin_code = admin[5]
                
                # Check if the user to be updated exists and belongs to same organization
                cursor.execute("SELECT * FROM users WHERE user_id=? AND code=?", (user_id_to_update, admin_code))
                user = cursor.fetchone()
                if not user:
                    return {"status": "User does not exist or does not belong to the same organization"}
                
                # Update user status
                cursor.execute("UPDATE users SET status=? WHERE user_id=?", (new_status, user_id_to_update))
                conn.commit()
                return {"status": "success"}
        except Exception as e:
            return {"status": "Error: " + str(e)}
    
    def login(self, email, password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the email and password match
                cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
                user = cursor.fetchone()
                if user:
                    user_id = user[0]
                    next_billing_date = user[8]  # Assuming the next_billing_date is at the 7th index
                    current_date = datetime.now().date()
                    # Check if current date is before the next billing date
                    if current_date < datetime.strptime(next_billing_date, "%Y-%m-%d").date():
                        return {"status": "success", "user": user_id}
                    else:
                        return {"status": "billing required"}
                else:
                    return {"status": "Invalid email or password"}
        except Exception as e:
            return {"status": "Error: " + str(e)}

    def admin_login(self, email, password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the email and password match for admin login
                cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
                user = cursor.fetchone()
                if user:
                    user_id = user[0]
                    return {"status": "success","user":user_id}
                else:
                    return {"status": "Invalid email or password"}
        except Exception as e:
            return {"status": "Error: " + str(e)}

    def change_password(self, user_id, old_password, new_password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if the old password matches
                cursor.execute("SELECT * FROM users WHERE user_id=? AND password=?", (user_id, old_password))
                user = cursor.fetchone()
                if user:
                    # Update password
                    cursor.execute("UPDATE users SET password=? WHERE user_id=?", (new_password, user_id))
                    conn.commit()
                    return {"status": "success"}
                else:
                    return {"status": "Invalid Password"}
        except Exception as e:
            return {"status": "Error: " + str(e)}
        
    def subscribe_user(self, user_id, next_date):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET next_date=?, status='Subscribed' WHERE user_id=?", (next_date, user_id))
                conn.commit()
                return {'status':'success'}
        except Exception as e:
            return {"status": "Error: " + str(e)}

    def subscribe_org(self, code, next_date):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET next_date=?, status='Subscribed' WHERE code=?", (code, next_date))
                conn.commit()
                return {'status':'success'}
        except Exception as e:
            return {"status": "Error: " + str(e)}

    def user_profile(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
                user = cursor.fetchone()
                if user:
                    # Base response
                    response = { "status": "success", "name": user[1], "email": user[2], "phone": user[3], "user_type": user[4], "code": user[5], "status": user[7], "next_date": user[8], "isadmin": user[10]}

                    # Add lawfirm name if user type is "org"
                    if user[4] == "org":
                        response["lawfirm_name"] = user[6]
                    
                    return response
                else:
                    return {"status": "User does not exist"}
        except Exception as e:
            print("Error on loading profile: " + str(e))
            return {"status": "Error: " + str(e)}

    def profiles(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
                users = cursor.fetchall()
                users_ = []
                for user in users:
                    # Base response  
                    user_data = {"user_id": user[0], "name": user[1], "email": user[2], "phone": user[3], "user_type": user[4], "code": user[5], "status": user[7], "next_date": user[8], "isadmin": user[10], "date_joined": user[11]}
                    
                    # Add lawfirm name if user type is "org"
                    if user[4] == "org":
                        user_data["lawfirm_name"] = user[6]   
                        
                    users_.append(user_data)
                return users_
        except Exception as e:
            print("Error on loading profiles: " + str(e))
            return []

