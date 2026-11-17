import os, uuid, hashlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
database_url = os.environ.get("DATABASE_URL", "sqlite:///bigboss.db")
# Render/Neon provide standard PostgreSQL URLs; use psycopg 3 with SQLAlchemy.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "1") == "1"
db = SQLAlchemy(app)

def india_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()

class VotingWeek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False, unique=True)
    title = db.Column(db.String(120), nullable=False)
    is_open = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Contestant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("voting_week.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    photo_url = db.Column(db.String(500), default="")
    votes = db.relationship("Vote", backref="contestant", lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("voting_week.id"), nullable=False)
    contestant_id = db.Column(db.Integer, db.ForeignKey("contestant.id"), nullable=False)
    voter_hash = db.Column(db.String(64), nullable=False)
    vote_date = db.Column(db.Date, nullable=False, default=india_today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("voter_hash", "vote_date", name="one_vote_per_browser_per_day"),)

def get_voter_token():
    token = request.cookies.get("bb_voter")
    return token or str(uuid.uuid4())

def hash_token(token):
    return hashlib.sha256((app.config["SECRET_KEY"] + token).encode()).hexdigest()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/robots.txt")
def robots():
    return "User-agent: *\nAllow: /\nSitemap: " + request.url_root.rstrip("/") + "/sitemap.xml\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/sitemap.xml")
def sitemap():
    base = request.url_root.rstrip("/")
    xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
           "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
           f"<url><loc>{base}/</loc></url><url><loc>{base}/results</loc></url>"
           "</urlset>")
    return xml, 200, {"Content-Type": "application/xml; charset=utf-8"}

@app.route("/")
def home():
    week = VotingWeek.query.filter_by(is_open=True).order_by(VotingWeek.week_number.desc()).first()
    if not week:
        return render_template("index.html", week=None, contestants=[], totals={}, total_votes=0, voted=False)
    contestants = Contestant.query.filter_by(week_id=week.id).order_by(Contestant.name).all()
    totals = {c.id: Vote.query.filter_by(week_id=week.id, contestant_id=c.id).count() for c in contestants}
    total_votes = sum(totals.values())
    token = request.cookies.get("bb_voter")
    voted = bool(token and Vote.query.filter_by(voter_hash=hash_token(token), vote_date=india_today()).first())
    return render_template("index.html", week=week, contestants=contestants, totals=totals, total_votes=total_votes, voted=voted)

@app.post("/vote")
def cast_vote():
    week = VotingWeek.query.filter_by(is_open=True).order_by(VotingWeek.week_number.desc()).first()
    if not week:
        flash("Voting is currently closed.")
        return redirect(url_for("home"))
    contestant_id = request.form.get("contestant_id", type=int)
    contestant = Contestant.query.filter_by(id=contestant_id, week_id=week.id).first()
    if not contestant:
        abort(400)
    token = get_voter_token()
    voter_hash = hash_token(token)
    if Vote.query.filter_by(voter_hash=voter_hash, vote_date=india_today()).first():
        flash("You have already voted today. Please come back tomorrow!")
    else:
        try:
            db.session.add(Vote(week_id=week.id, contestant_id=contestant.id, voter_hash=voter_hash, vote_date=india_today()))
            db.session.commit()
            flash("Your vote has been recorded. Thank you!")
        except Exception:
            db.session.rollback()
            flash("A vote from this browser has already been recorded today.")
    response = make_response(redirect(url_for("home")))
    response.set_cookie("bb_voter", token, max_age=60*60*24*365, httponly=True, samesite="Lax", secure=os.environ.get("COOKIE_SECURE") == "1")
    return response

@app.route("/results")
def results():
    week = VotingWeek.query.order_by(VotingWeek.week_number.desc()).first()
    if not week:
        return render_template("results.html", week=None, rows=[], total=0)
    contestants = Contestant.query.filter_by(week_id=week.id).all()
    rows = [(c, Vote.query.filter_by(week_id=week.id, contestant_id=c.id).count()) for c in contestants]
    total = sum(v for _, v in rows)
    rows.sort(key=lambda item: item[1], reverse=True)
    return render_template("results.html", week=week, rows=rows, total=total)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        stored_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
        password = request.form.get("password", "")
        if stored_hash and check_password_hash(stored_hash, password):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Invalid password. Configure ADMIN_PASSWORD_HASH before logging in.")
    return render_template("login.html")

@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_week":
            number = request.form.get("week_number", type=int)
            title = request.form.get("title", "").strip()
            names = [x.strip() for x in request.form.get("contestants", "").splitlines() if x.strip()]
            if not number or not title or not names:
                flash("Enter a week number, title and at least one contestant.")
            elif VotingWeek.query.filter_by(week_number=number).first():
                flash("That week number already exists.")
            else:
                week = VotingWeek(week_number=number, title=title, is_open=True)
                db.session.add(week)
                db.session.flush()
                for name in names:
                    db.session.add(Contestant(week_id=week.id, name=name))
                db.session.commit()
                flash("Nomination week created.")
        elif action == "toggle":
            week = VotingWeek.query.get_or_404(request.form.get("week_id", type=int))
            week.is_open = not week.is_open
            db.session.commit()
            flash("Voting status updated.")
        elif action == "add_contestant":
            week = VotingWeek.query.get_or_404(request.form.get("week_id", type=int))
            name = request.form.get("name", "").strip()
            photo = request.form.get("photo_url", "").strip()
            if name:
                db.session.add(Contestant(week_id=week.id, name=name, photo_url=photo))
                db.session.commit()
                flash("Contestant added.")
        elif action == "delete_contestant":
            contestant = Contestant.query.get_or_404(request.form.get("contestant_id", type=int))
            Vote.query.filter_by(contestant_id=contestant.id).delete()
            db.session.delete(contestant)
            db.session.commit()
            flash("Contestant and their votes were deleted.")
        return redirect(url_for("admin"))
    weeks = VotingWeek.query.order_by(VotingWeek.week_number.desc()).all()
    return render_template("admin.html", weeks=weeks)

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database tables created.")

# Create tables when the production WSGI server imports this module.
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
