# Raffle Application

A Flask-based web application for hosting raffles.

## Features (Phases 1 & 2)

*   User registration and login (admin role for the first registered user).
*   Admins can create and edit raffles, including item name, description, image (via upload), ticket price, and end time.
*   Users can view active raffles with live countdown timers.
*   Users can purchase tickets for active raffles.
*   Users can view tickets they've purchased on a "My Tickets" page.
*   Automatic random winner selection when a raffle's end time is reached, managed by APScheduler.
*   Manual admin override for drawing winners if needed.
*   Admin dashboard to view raffles and users.
*   Motorbike-inspired dark theme.

## Project Structure

*   `app.py`: Main Flask application, routes, models, and scheduler logic.
*   `requirements.txt`: Python dependencies.
*   `static/`: CSS, JavaScript, and uploaded images.
    *   `css/style.css`: Main stylesheet.
    *   `js/scripts.js`: JavaScript for countdowns, etc.
    *   `uploads/`: Directory where raffle item images are stored.
*   `templates/`: HTML templates for rendering pages.
*   `instance/site.db`: SQLite database file (created automatically).

## Setup and Running

1.  **Clone the Repository (if applicable)**
    *   If you have this project from a Git repository, clone it first.

2.  **Create and Activate a Virtual Environment (Recommended)**
    *   Navigate to the `raffle_app` directory in your terminal.
    *   Create a virtual environment:
        ```bash
        python -m venv venv
        # Or: python3 -m venv venv
        ```
    *   Activate it:
        *   Linux/macOS: `source venv/bin/activate`
        *   Windows: `venv\Scripts\activate`

3.  **Install Dependencies**
    *   With your virtual environment active, install the required packages:
        ```bash
        pip install -r requirements.txt
        ```

4.  **Run the Application**
    *   Execute the main application file:
        ```bash
        python app.py
        ```
    *   The application will typically be available at `http://127.0.0.1:5000/`.
    *   You will see console output from Flask and APScheduler.

## Testing the Application

Follow these steps to test the various features:

**1. User Accounts**
    *   Open `http://127.0.0.1:5000/` in your browser.
    *   Click "Register". Create User A. **This first user (User A) is automatically an Admin.**
    *   Log out.
    *   Click "Register" again. Create User B (this will be a Normal User).
    *   Test logging in and out with both User A (Admin) and User B (Normal). Observe differences in navigation links (e.g., Admin Dashboard, Create Raffle for admin).

**2. Admin: Create Raffles for Testing**
    *   Log in as User A (Admin).
    *   Navigate to "Create Raffle" (or "Admin Dashboard" -> "Create one now!").
    *   **Raffle 1 (for Auto-Draw Test):**
        *   Name: e.g., "Auto Draw Test Bike"
        *   Description: Any text.
        *   Item Image: Upload a small JPG, PNG, or GIF.
        *   Ticket Price: e.g., 1 or 5.
        *   **End Time:** Choose a date and time that is approximately **5-7 minutes in the future** from your current system time. This is crucial for testing the scheduler.
        *   Click "Create Raffle".
        *   **Observe Console:** You should see a log message like: `APScheduler: Scheduled job draw_winner_for_raffle_X for raffle X at YYYY-MM-DD HH:MM:SS`.
    *   **Raffle 2 (for Manual Draw & Ended Display Test):**
        *   Name: e.g., "Manual Draw Helmet"
        *   Description: Any text.
        *   Item Image: Upload another image.
        *   Ticket Price: e.g., 2.
        *   **End Time:** Choose a date and time that is **in the past** (e.g., yesterday).
        *   Click "Create Raffle". (No scheduler message for this one as its end time is past).

**3. Viewing Raffles & UI Elements**
    *   As any user (or logged out), go to "View Raffles".
    *   For "Auto Draw Test Bike":
        *   Verify the "Time Left" countdown is active and ticking down.
        *   Note the general theme, colors, and layout.
    *   For "Manual Draw Helmet":
        *   It should show as "Raffle Ended".
    *   Click "View Details & Buy Ticket" (or "View Details") for each raffle to go to their detail pages.
        *   Verify countdowns and information display correctly on detail pages.

**4. Normal User: Purchasing Tickets**
    *   Log in as User B (Normal User).
    *   Navigate to "View Raffles" and find "Auto Draw Test Bike". Click "View Details & Buy Ticket".
    *   Click the "Buy Ticket" button. You should see a success message.
    *   Purchase another ticket for the same raffle if you wish.
    *   Navigate to "My Tickets" (from top navigation). Verify your purchased ticket(s) are listed.
    *   (Optional) Buy a ticket for "Manual Draw Helmet" as well, to test winner display later.

**5. Testing Automatic Winner Selection (APScheduler)**
    *   This tests "Auto Draw Test Bike".
    *   Ensure at least one ticket was purchased for it.
    *   Keep the `python app.py` console window visible.
    *   **Wait** for the raffle's specified end time to arrive and pass.
    *   **Observe Console:** Around the exact end time, you should see log messages from APScheduler:
        *   `APScheduler: Attempting to draw winner for raffle ID: X`
        *   `APScheduler: Winner for 'Auto Draw Test Bike' (ID: X) is 'UserBUsername'! Raffle updated.` (Assuming User B bought the ticket).
    *   **Verify in Web Application:**
        *   Refresh the "View Raffles" page or the detail page for "Auto Draw Test Bike".
        *   It should now state "Raffle Ended" and display the winner's username correctly.
        *   If User B won, log in as User B, go to "My Tickets". It should indicate the win.

**6. Testing Drawing Placeholder & Manual Admin Draw**
    *   This tests "Manual Draw Helmet".
    *   Log in as User A (Admin).
    *   Navigate to the detail page for "Manual Draw Helmet".
    *   Since it has ended and no winner is drawn, you should see:
        *   "The raffle has ended!"
        *   "The winner will be drawn soon. Good luck!"
        *   A spinner animation and "Awaiting Winner Selection...".
    *   Click the "Draw Winner Now" button. Confirm the action.
    *   The page should refresh (or redirect), and the winner should now be displayed for "Manual Draw Helmet".

**7. Admin: Editing a Raffle & Rescheduling**
    *   Log in as User A (Admin).
    *   Go to "Admin Dashboard".
    *   Find "Auto Draw Test Bike" (which has now ended). Click "Edit".
    *   Change its **End Time** to be **10 minutes in the future** from now.
    *   (Optional) Change other details like description or upload a new image.
    *   Click "Save Changes".
    *   **Observe Console:** You should see messages indicating the job for this raffle was likely removed and then re-scheduled for the new future time.
        *   `APScheduler: Removed existing job draw_winner_for_raffle_X ...` (if it was still somehow there or if logic always tries to remove)
        *   `APScheduler: Scheduled job draw_winner_for_raffle_X for raffle X at (new future time)`
    *   The raffle should now appear as active again on the "View Raffles" page with a new countdown. Let it run to test the rescheduled automatic draw.

**8. Testing APScheduler Job Persistence**
    *   Log in as User A (Admin).
    *   Create a new raffle: "Persistence Test Raffle". Set its end time for **~5-7 minutes in the future**.
    *   **Observe Console:** Confirm the job is scheduled: `APScheduler: Scheduled job ...`
    *   Go to the terminal where `python app.py` is running and **stop the application** (Ctrl+C).
    *   **Restart the application:** `python app.py`.
    *   **Observe Console:** APScheduler should indicate it's starting and might log information about loaded jobs from its job store.
    *   **Wait** for the original scheduled end time of "Persistence Test Raffle".
    *   The automatic draw should still occur. Check the console for draw messages and verify the winner in the web application. This confirms jobs persist across application restarts.

**9. Admin Dashboard Overview**
    *   Log in as User A (Admin). Go to "Admin Dashboard".
    *   Review the "Manage Raffles" table: Check if statuses (Active/Ended), end times, and winner information are accurate. Test the "View" and "Edit" links.
    *   Review the "Manage Users" table: Check if user details and ticket counts are correct.

This guide should help in verifying all implemented features. Pay close attention to console logs for APScheduler activity and any potential errors.
```
