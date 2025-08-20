import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- App & Database Configuration ---

# Get the base directory of the project
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# A secret key is required for session management and flash messages
app.config['SECRET_KEY'] = 'your_super_secret_key_change_this' 
# Configure the database URI. This will create a file named 'portfolio.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'portfolio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    featured_image_url = db.Column(db.String(255), nullable=False)
    is_featured = db.Column(db.Boolean, default=False)
    paintings = db.relationship('Painting', backref='category', lazy=True, cascade="all, delete-orphan")

class Painting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    is_sold = db.Column(db.Boolean, default=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)


# --- Custom Flask CLI Commands to set up the database and admin ---

@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables."""
    db.create_all()
    print("Initialized the database.")

@app.cli.command("create-admin")
def create_admin_command():
    """Creates the admin user."""
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin = User(username='admin')
        admin.set_password('admin123') # IMPORTANT: Change this password
        db.session.add(admin)
        db.session.commit()
        print("Admin user created with username 'admin' and password 'admin123'.")
    else:
        print("Admin user already exists.")


# --- Public-Facing Routes ---

@app.route('/')
def home():
    featured_categories = Category.query.filter_by(is_featured=True).all()
    paintings = Painting.query.filter_by(is_sold=False).order_by(Painting.id.desc()).all()
    return render_template('index.html', featured_categories=featured_categories, paintings=paintings)

@app.route('/category/<string:category_name>')
def category_page(category_name):
    category = Category.query.filter_by(name=category_name).first_or_404()
    paintings = Painting.query.filter_by(category=category, is_sold=False).all()
    return render_template('category.html', paintings=paintings, category_name=category.name)

@app.route('/product/<int:product_id>')
def product(product_id):
    painting = Painting.query.get_or_404(product_id)
    return render_template('product.html', painting=painting)


# --- Authentication Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        error = None
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            error = 'Invalid username or password.'
        
        if error is None:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('admin'))

        flash(error)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# --- Admin-Only Routes ---

def is_admin():
    """Helper function to check if a user is logged in."""
    return 'user_id' in session

@app.route('/admin')
def admin():
    if not is_admin():
        return redirect(url_for('login'))
    
    paintings = Painting.query.all()
    categories = Category.query.all()
    return render_template('admin.html', paintings=paintings, categories=categories)

@app.route('/admin/add_painting', methods=['POST'])
def add_painting():
    if not is_admin():
        return redirect(url_for('login'))

    title = request.form.get('title')
    description = request.form.get('description')
    price = request.form.get('price')
    image_url = request.form.get('image_url')
    category_name = request.form.get('category')
    
    category = Category.query.filter_by(name=category_name).first()
    
    if category:
        new_painting = Painting(
            title=title, 
            description=description, 
            price=float(price), 
            image_url=image_url, 
            category_id=category.id
        )
        db.session.add(new_painting)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/add_category', methods=['POST'])
def add_category():
    if not is_admin():
        return redirect(url_for('login'))

    name = request.form.get('name')
    featured_image_url = request.form.get('featured_image_url')
    is_featured = 'is_featured' in request.form

    new_category = Category(
        name=name, 
        featured_image_url=featured_image_url,
        is_featured=is_featured
    )
    db.session.add(new_category)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/edit/<int:painting_id>', methods=['GET', 'POST'])
def edit_painting(painting_id):
    if not is_admin():
        return redirect(url_for('login'))

    painting = Painting.query.get_or_404(painting_id)
    
    if request.method == 'POST':
        # Update painting details from the form
        painting.title = request.form.get('title')
        painting.description = request.form.get('description')
        painting.price = float(request.form.get('price'))
        painting.image_url = request.form.get('image_url')
        category_name = request.form.get('category')
        category = Category.query.filter_by(name=category_name).first()
        if category:
            painting.category_id = category.id
        db.session.commit()
        return redirect(url_for('admin'))

    # For a GET request, show the edit form
    categories = Category.query.all()
    return render_template('edit_painting.html', painting=painting, categories=categories)

@app.route('/admin/delete/<int:painting_id>', methods=['POST'])
def delete_painting(painting_id):
    if not is_admin():
        return redirect(url_for('login'))
        
    painting = Painting.query.get_or_404(painting_id)
    db.session.delete(painting)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/toggle_sold/<int:painting_id>', methods=['POST'])
def toggle_sold(painting_id):
    if not is_admin():
        return redirect(url_for('login'))

    painting = Painting.query.get_or_404(painting_id)
    painting.is_sold = not painting.is_sold
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/delete_category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    if not is_admin():
        return redirect(url_for('login'))

    # Find the category in the database by its ID
    category_to_delete = Category.query.get_or_404(category_id)
    @app.route('/admin/edit_category/<int:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    if not is_admin():
        return redirect(url_for('login'))

    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.featured_image_url = request.form.get('featured_image_url')
        category.is_featured = 'is_featured' in request.form
        db.session.commit()
        flash(f"Category '{category.name}' has been updated.", "success")
        return redirect(url_for('admin'))

    return render_template('edit_category.html', category=category)
    
    # Thanks to the 'cascade' setting in our database model,
    # SQLAlchemy will automatically delete all paintings associated with this category.
    db.session.delete(category_to_delete)
    db.session.commit()
    
    flash(f"Category '{category_to_delete.name}' and all its paintings have been deleted.", "success")
    return redirect(url_for('admin'))
