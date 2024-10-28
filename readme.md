# Web_Store

## Introduction
This is a web-based e-commerce application for selling items online. It supports product browsing, filtering, user authentication, cart management, and order processing. Below are instructions on how to set up and run the project.



## Technology stack
- Python 3.9+
- Flask
- SQLAlchemy ORM
- Flask-login
- Flask-WTF
- Other dependencies listed in the `requirements.txt` file.

## Functionality
- Registration and authorization of users
- Session based shopping cart
- Ability to add categories and products
- Admin dashboard

## Installation Guide
1. Clone git repository
2. Install a Virtual Environment.
3. Install the dependencies.
```
pip install -r requirements.txt  
```
4. Open the Flask shell to create DB:
```
flask shell
```
```
from app.models import Post, User, Profile
```
```
db.create_all()
```
5. Exit the flask shell `Ctrl+Z`,`Enter`
6. Run the application.

