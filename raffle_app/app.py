from flask import Flask, render_template, request, redirect, url_for, flash
import datetime
import random
import os
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# For clarity, let's specify the exact datetime imports needed if they are not already broad
from datetime import datetime as dt # Alias to avoid conflict if 'datetime' module also used
from datetime import time as dt_time # For time object

import pytz # Should have been added in step 1 of this plan (install pytz)

# Add these imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger
import atexit # To shut down scheduler on app exit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Assuming forms.py is created in the raffle_app directory
# from forms import RegistrationForm, LoginForm # This will cause an import error if forms.py tries to import User from app.py

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_here' # Replace with a real secret key
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db' # Must be defined before using in jobstores
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure APScheduler
# The job store will use the same database as Flask-SQLAlchemy
jobstores = {
    'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
}
scheduler = BackgroundScheduler(jobstores=jobstores)

# The actual function that draws the winner
def scheduled_draw_winner(raffle_id_to_draw, app_context):
    with app_context: # Need app context to access db, current_app, etc.
        print(f"APScheduler: Attempting to draw winner for raffle ID: {raffle_id_to_draw}")
        raffle = Raffle.query.get(raffle_id_to_draw) # Use get instead of get_or_404 for background task

        if not raffle:
            print(f"APScheduler: Raffle ID {raffle_id_to_draw} not found. Cannot draw winner.")
            return

        if raffle.winner_id is not None:
            print(f"APScheduler: Winner for '{raffle.name}' (ID: {raffle_id_to_draw}) already drawn. Skipping.")
            return

        # Check end time again, though job is scheduled for end_time
        # This is more of a safeguard or if coalesce=True and job is late
        if raffle.end_time > datetime.datetime.utcnow():
            print(f"APScheduler: Raffle '{raffle.name}' (ID: {raffle_id_to_draw}) has not officially ended yet according to current time. Rescheduling or skipping.")
            # Optionally reschedule if this scenario is problematic, or just log and skip.
            # For now, we assume the job trigger is accurate.
            # return

        tickets = Ticket.query.filter_by(raffle_id=raffle.id).all()

        if not tickets:
            print(f"APScheduler: No tickets sold for '{raffle.name}' (ID: {raffle_id_to_draw}). Cannot draw winner.")
            # Optionally, set a status on the raffle indicating no winner due to no tickets
            raffle.winner_id = None # Explicitly ensure it's None or a special value
            # db.session.add(RaffleStatus(raffle_id=raffle.id, status_message="No tickets sold"))
            db.session.commit()
            return

        winner_ticket = random.choice(tickets)
        raffle.winner_id = winner_ticket.user_id
        db.session.commit()

        winner_user = User.query.get(raffle.winner_id)
        winner_username = winner_user.username if winner_user else f"ID {raffle.winner_id}"
        print(f"APScheduler: Winner for '{raffle.name}' (ID: {raffle_id_to_draw}) is {winner_username}! Raffle updated.")
        # Here you could also trigger notifications (e.g., email) in a more advanced setup

# Helper function to schedule a draw
def schedule_raffle_draw_job(raffle_id, run_date, current_app_context):
    job_id = f'draw_winner_for_raffle_{raffle_id}'
    try:
        # Remove existing job first if it exists, to handle updates
        scheduler.remove_job(job_id)
        print(f"APScheduler: Removed existing job {job_id} before rescheduling.")
    except Exception as e: # apscheduler.jobstores.base.JobLookupError if job doesn't exist
        print(f"APScheduler: No existing job {job_id} to remove or other error: {e}")

    if run_date > datetime.datetime.utcnow():
        scheduler.add_job(
            func=scheduled_draw_winner,
            trigger=DateTrigger(run_date=run_date),
            args=[raffle_id, current_app_context], # Pass app_context here
            id=job_id,
            replace_existing=True # This should also handle updates if job_id matches
        )
        print(f"APScheduler: Scheduled job {job_id} for raffle {raffle_id} at {run_date}")
    else:
        print(f"APScheduler: Raffle {raffle_id} end time {run_date} is in the past. Not scheduling draw job.")

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
    item_image_filename = db.Column(db.String(100), nullable=True) # New field
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
from flask_wtf.file import FileField, FileAllowed # Add this
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, FloatField, DateTimeField, DateField # Added DateField
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
    item_image = FileField('Item Image (jpg, jpeg, png, gif)', validators=[
        Optional(), # Make it optional, especially for editing
        FileAllowed(app.config['ALLOWED_EXTENSIONS'], 'Images only!')
    ])
    ticket_price = FloatField('Ticket Price', validators=[DataRequired()])

    # Old field:
    # end_time = DateTimeField('End Time (YYYY-MM-DD HH:MM:SS)', format='%Y-%m-%d %H:%M:%S', validators=[DataRequired()])

    # New field:
    end_date = DateField('Raffle End Date (defaults to 8 PM Eastern Time)', validators=[DataRequired()])

    submit = SubmitField('Create Raffle') # Text will be changed in template for edit forms

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
        filename = None
        if form.item_image.data:
            file = form.item_image.data
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                flash('Invalid image file type.', 'danger')
                return render_template('create_raffle.html', title='Create Raffle', form=form)

        # Get the date from the form
        selected_date = form.end_date.data # This is a Python date object

        # Define target time and timezone
        target_time = dt_time(20, 0, 0) # 8 PM
        est_tz = pytz.timezone('America/New_York')

        # Combine date and time to create a naive datetime
        naive_datetime = dt.combine(selected_date, target_time)

        # Localize the naive datetime to EST
        est_datetime = est_tz.localize(naive_datetime)

        # Convert EST datetime to UTC
        utc_datetime = est_datetime.astimezone(pytz.utc)

        # Let's get current time in UTC (aware) for proper comparison
        now_utc_aware = pytz.utc.localize(dt.utcnow())

        if utc_datetime <= now_utc_aware:
            flash('The selected date (ending 8 PM EST) must be in the future.', 'danger')
        else:
            raffle = Raffle(
                name=form.name.data,
                description=form.description.data,
                item_image_filename=filename,
                ticket_price=form.ticket_price.data,
                end_time=utc_datetime, # Store the calculated UTC datetime
                created_by_user_id=current_user.id
            )
            db.session.add(raffle)
            db.session.commit() # Commit to get raffle.id

            # Schedule the draw job with the UTC datetime
            schedule_raffle_draw_job(raffle.id, raffle.end_time, app.app_context())

            flash(f'Raffle "{raffle.name}" has been created successfully! It will end on {selected_date.strftime("%Y-%m-%d")} at 8 PM Eastern Time and the draw is scheduled.', 'success')
            return redirect(url_for('admin_dashboard'))

    elif request.method == 'POST':
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

@app.route('/raffle/<int:raffle_id>')
def raffle_detail(raffle_id):
    raffle = Raffle.query.get_or_404(raffle_id)
    # Pass now_utc for countdown consistency
    return render_template('raffle_detail.html', title=raffle.name, raffle=raffle, now_utc=datetime.datetime.utcnow())

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    raffles = Raffle.query.order_by(Raffle.start_time.desc()).all()
    users = User.query.order_by(User.username).all() # Optional: fetch users
    return render_template('admin_dashboard.html', title='Admin Dashboard', raffles=raffles, users=users, now_utc=datetime.datetime.utcnow())

@app.route('/admin/edit_raffle/<int:raffle_id>', methods=['GET', 'POST'])
@login_required
def edit_raffle(raffle_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    raffle = Raffle.query.get_or_404(raffle_id)
    form = RaffleForm(obj=raffle) # Pre-populates most fields

    est_tz = pytz.timezone('America/New_York')

    if request.method == 'GET':
        if raffle.end_time:
            # Convert stored naive UTC end_time to aware UTC, then to EST for display
            utc_end_time_aware = pytz.utc.localize(raffle.end_time)
            est_end_time_display = utc_end_time_aware.astimezone(est_tz)
            form.end_date.data = est_end_time_display.date()

    if form.validate_on_submit():
        # File handling logic
        new_image_filename_to_save = raffle.item_image_filename
        if form.item_image.data and form.item_image.data.filename != '':
            file = form.item_image.data
            if allowed_file(file.filename):
                new_image_filename_to_save = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_image_filename_to_save))
            else:
                flash('Invalid image file type for new image.', 'danger')
                if raffle.end_time: # Re-populate date for template display on error
                    utc_end_time_aware = pytz.utc.localize(raffle.end_time)
                    est_end_time_display = utc_end_time_aware.astimezone(est_tz)
                    form.end_date.data = est_end_time_display.date()
                return render_template('edit_raffle.html', title=f'Edit {raffle.name}', form=form, raffle=raffle)

        # Date and Time processing from form.end_date
        selected_date = form.end_date.data
        target_time = dt_time(20, 0, 0) # 8 PM EST
        naive_datetime_form = dt.combine(selected_date, target_time)
        est_datetime_form = est_tz.localize(naive_datetime_form)
        utc_datetime_form_aware = est_datetime_form.astimezone(pytz.utc)

        now_utc_aware = pytz.utc.localize(dt.utcnow())

        original_utc_aware = pytz.utc.localize(raffle.end_time) if raffle.end_time else None
        is_end_time_changed_meaningfully = (original_utc_aware != utc_datetime_form_aware)

        if is_end_time_changed_meaningfully and utc_datetime_form_aware <= now_utc_aware:
            flash('The new end date (ending 8 PM EST) must be in the future if changed.', 'danger')
            if raffle.end_time: # Re-populate for template display on error
                current_utc_end_time = pytz.utc.localize(raffle.end_time)
                current_est_end_time = current_utc_end_time.astimezone(est_tz)
                form.end_date.data = current_est_end_time.date()
            return render_template('edit_raffle.html', title=f'Edit {raffle.name}', form=form, raffle=raffle)

        # Update raffle object
        raffle.name = form.name.data
        raffle.description = form.description.data
        raffle.item_image_filename = new_image_filename_to_save
        raffle.ticket_price = form.ticket_price.data

        new_naive_utc_for_storage = None
        if is_end_time_changed_meaningfully or not raffle.end_time:
             raffle.end_time = utc_datetime_form_aware.replace(tzinfo=None) # Store as naive UTC
             new_naive_utc_for_storage = raffle.end_time
        # else, raffle.end_time (already naive UTC) remains unchanged if not meaningfully different

        db.session.commit()

        if is_end_time_changed_meaningfully or \
           (original_utc_aware and original_utc_aware <= now_utc_aware and new_naive_utc_for_storage and new_naive_utc_for_storage > dt.utcnow()):
            schedule_raffle_draw_job(raffle.id, new_naive_utc_for_storage if new_naive_utc_for_storage else raffle.end_time, app.app_context())

        flash(f'Raffle "{raffle.name}" has been updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    elif request.method == 'POST' and not form.validate_on_submit():
        if raffle.end_time and not form.end_date.data:
            utc_end_time = pytz.utc.localize(raffle.end_time)
            est_end_time_display = utc_end_time.astimezone(est_tz)
            form.end_date.data = est_end_time_display.date()
        flash('Please correct the errors in the form.', 'danger')

    return render_template('edit_raffle.html', title=f'Edit {raffle.name}', form=form, raffle=raffle)

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Ensure all tables, including APScheduler's, are created

    # It's important to start the scheduler only once, typically not in debug mode reloader.
    # For development, it might run multiple times if reloader is active.
    # A common pattern is to only start it if not in debug mode or if os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    # For simplicity now, we start it.
    try:
        scheduler.start()
        print("APScheduler started...")
    except Exception as e:
        print(f"Error starting APScheduler: {e}")

    atexit.register(lambda: scheduler.shutdown())
    app.run(debug=True) # Or your production server command
else:
    # If using a production server like Gunicorn, scheduler might need to be started differently
    # (e.g., in a post_worker_init hook or a separate worker process for the scheduler).
    # For now, this simple setup assumes flask dev server or a single process server.
    # If scheduler is already running (e.g. due to reloader), start() might raise an error.
    if not scheduler.running:
        try:
            scheduler.start()
            print("APScheduler started (non-main context)...")
        except Exception as e:
            print(f"Error starting APScheduler (non-main context): {e}")
    atexit.register(lambda: scheduler.shutdown())
