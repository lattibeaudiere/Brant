from flask import Flask, render_template, request, redirect, url_for, flash
import datetime
import random
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Assuming forms.py is created in the raffle_app directory
# from forms import RegistrationForm, LoginForm # This will cause an import error if forms.py tries to import User from app.py

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_here' # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Route to redirect to if @login_required is used
login_manager.login_message_category = 'info'


class User(db.Model, UserMixin): # Add UserMixin
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    tickets = db.relationship('Ticket', foreign_keys='Ticket.user_id', backref='user', lazy='dynamic')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Raffle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    item_image_url = db.Column(db.String(200), nullable=True)
    ticket_price = db.Column(db.Float, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Optional: who created it
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    winner = db.relationship('User', foreign_keys=[winner_id])

    # Relationships (optional but good for ORM convenience)
    # creator = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_raffles') # If tracking creator
    # winner = db.relationship('User', foreign_keys=[winner_id], backref='won_raffles') # If tracking winner

    def __repr__(self):
        return f'<Raffle {self.name}>'

    tickets = db.relationship('Ticket', foreign_keys='Ticket.raffle_id', backref='raffle', lazy='dynamic')

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    raffle_id = db.Column(db.Integer, db.ForeignKey('raffle.id'), nullable=False)

    def __repr__(self):
        return f'<Ticket {self.id} for Raffle {self.raffle_id} by User {self.user_id}>'

# Moved forms to app.py to avoid circular import issues for now
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, FloatField, DateTimeField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional
# import datetime # Already imported for Raffle model

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


@app.route('/')
def home():
    return render_template('index.html', title='Home')

class RaffleForm(FlaskForm):
    name = StringField('Raffle Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    item_image_url = StringField('Item Image URL', validators=[Optional(), Length(max=200)]) # Consider FileField later
    ticket_price = FloatField('Ticket Price', validators=[DataRequired()])
    # For DateTimeField, format might be needed depending on how it's handled or use WTForms-Alchemy
    end_time = DateTimeField('End Time (YYYY-MM-DD HH:MM:SS)', format='%Y-%m-%d %H:%M:%S', validators=[DataRequired()])
    submit = SubmitField('Create Raffle')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        # To make the first registered user an admin:
        is_first_user_admin = not User.query.first()
        user = User(username=form.username.data, password_hash=hashed_password, is_admin=is_first_user_admin)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        if is_first_user_admin:
            flash('You have been registered as an admin.', 'info')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/create_raffle', methods=['GET', 'POST'])
@login_required
def create_raffle():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    form = RaffleForm()
    if form.validate_on_submit():
        # Ensure end_time is in the future if desired (add custom validator to form or check here)
        if form.end_time.data <= datetime.datetime.utcnow():
            flash('End time must be in the future.', 'danger')
        else:
            raffle = Raffle(
                name=form.name.data,
                description=form.description.data,
                item_image_url=form.item_image_url.data,
                ticket_price=form.ticket_price.data,
                end_time=form.end_time.data,
                created_by_user_id=current_user.id # Optional: set creator
            )
            db.session.add(raffle)
            db.session.commit()
            flash(f'Raffle "{raffle.name}" has been created successfully!', 'success')
            return redirect(url_for('home')) # Or redirect to a raffle details page
    elif request.method == 'POST':
        # Form did not validate, provide feedback if specific errors aren't shown by WTForms default
        flash('Please correct the errors in the form.', 'danger')

    return render_template('create_raffle.html', title='Create Raffle', form=form)

@app.route('/raffles')
def list_raffles():
    # Query all raffles for now, ordered by end_time perhaps
    # Later, filter by active (e.g., end_time > datetime.datetime.utcnow())
    raffles = Raffle.query.order_by(Raffle.end_time.asc()).all()
    return render_template('raffles.html', title='Active Raffles', raffles=raffles, now_utc=datetime.datetime.utcnow())

@app.route('/buy_ticket/<int:raffle_id>', methods=['POST']) # Should be POST to avoid accidental buys
@login_required
def buy_ticket(raffle_id):
    raffle = Raffle.query.get_or_404(raffle_id)

    # Check if raffle is still active
    if raffle.end_time <= datetime.datetime.utcnow():
        flash('This raffle has already ended.', 'danger')
        return redirect(url_for('list_raffles'))

    # Optional: Check if user has already bought max tickets (not implemented yet)
    # Optional: Check if tickets are still available (not implemented yet)

    # Create the ticket
    ticket = Ticket(user_id=current_user.id, raffle_id=raffle.id)
    db.session.add(ticket)
    db.session.commit()

    flash(f'You have successfully purchased a ticket for "{raffle.name}"!', 'success')
    return redirect(url_for('list_raffles')) # Or redirect to a 'my_tickets' page

@app.route('/my_tickets')
@login_required
def my_tickets():
    # Sorter by purchase time, newest first
    # Need to pass now_utc to the template if it's used for display logic there for consistency
    tickets = Ticket.query.filter_by(user_id=current_user.id).order_by(Ticket.purchase_time.desc()).all()
    return render_template('my_tickets.html', title='My Tickets', tickets=tickets, now_utc=datetime.datetime.utcnow())

@app.route('/draw_winner/<int:raffle_id>', methods=['POST'])
@login_required
def draw_winner(raffle_id):
    if not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('list_raffles'))

    raffle = Raffle.query.get_or_404(raffle_id)

    if raffle.winner_id is not None:
        flash(f'Winner for "{raffle.name}" has already been drawn: {raffle.winner.username if raffle.winner else "User ID " + str(raffle.winner_id)}.', 'warning')
        return redirect(url_for('list_raffles'))

    if raffle.end_time > datetime.datetime.utcnow():
        flash(f'Raffle "{raffle.name}" has not ended yet. Cannot draw winner.', 'warning')
        return redirect(url_for('list_raffles'))

    tickets = Ticket.query.filter_by(raffle_id=raffle.id).all()

    if not tickets:
        flash(f'No tickets were sold for "{raffle.name}". Cannot draw a winner.', 'warning')
        # Optionally, mark the raffle as having no winner or handle differently
        return redirect(url_for('list_raffles'))

    winner_ticket = random.choice(tickets)
    raffle.winner_id = winner_ticket.user_id
    db.session.commit()

    # Fetch winner's username for the message (optional but nice)
    # winner_user = User.query.get(raffle.winner_id) # Not needed if using raffle.winner.username
    winner_username = raffle.winner.username if raffle.winner else f"ID {raffle.winner_id}"

    flash(f'Winner for "{raffle.name}" is {winner_username}! Congratulations!', 'success')
    return redirect(url_for('list_raffles'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
