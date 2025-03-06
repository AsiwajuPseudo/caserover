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
                              (user_id TEXT, name TEXT, email TEXT, phone TEXT,user_type TEXT,code TEXT,lawfirm_name TEXT,status TEXT,next_date TEXT, password TEXT, isadmin TEXT)''')
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
        next_billing_date = current_datetime + timedelta(days=7)
        next_date=str(next_billing_date.date())
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email=?", (email,))
                existing_user = cursor.fetchone()
                if existing_user:
                    return {"status": "Email already exists"}
                cursor.execute("INSERT INTO users (user_id, name, email, phone, user_type, code, lawfirm_name, status, next_date, password, isadmin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (user_id, name, email, phone,user_type, code, lawfirm_name, status, next_date, password, isadmin))
                conn.commit()
                return {"status": "success","user":user_id}
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
                    user_data = {"user_id": user[0], "name": user[1], "email": user[2], "phone": user[3], "user_type": user[4], "code": user[5], "status": user[7], "next_date": user[8], "isadmin": user[10]}
                    
                    # Add lawfirm name if user type is "org"
                    if user[4] == "org":
                        user_data["lawfirm_name"] = user[6]   
                        
                    users_.append(user_data)
                return users_
        except Exception as e:
            print("Error on loading profiles: " + str(e))
            return []

    def delete_user(self, user_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                conn.commit()
                return {"status":"success"}
        except Exception as e:
            return {"status":"Error: " + str(e)}
