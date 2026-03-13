from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date

app = Flask(__name__)

app.config["SECRET_KEY"] = "secret123"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///loan_system.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# =========================
# USER MODEL
# =========================
class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True)

    password = db.Column(db.String(200))

    role = db.Column(db.String(20))   # admin or officer


    def set_password(self, password):
        self.password = generate_password_hash(password)


    def check_password(self, password):
        return check_password_hash(self.password, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# BORROWER MODEL
# =========================
class Borrower(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))

    phone = db.Column(db.String(50))

    id_number = db.Column(db.String(50))

    officer_id = db.Column(db.Integer, db.ForeignKey("user.id"))


# =========================
# LOAN MODEL
# =========================
class Loan(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    borrower_id = db.Column(db.Integer)

    amount = db.Column(db.Float)

    interest = db.Column(db.Float)

    total = db.Column(db.Float)

    daily_payment = db.Column(db.Float)

    days = db.Column(db.Integer)

    start_date = db.Column(db.Date)


# =========================
# PAYMENT MODEL
# =========================
class Payment(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    loan_id = db.Column(db.Integer)

    amount = db.Column(db.Float)

    payment_date = db.Column(db.Date, default=date.today)


# =========================
# DATABASE INIT
# =========================
with app.app_context():

    db.create_all()

    admin = User.query.filter_by(username="admin").first()

    if not admin:

        admin = User(username="admin", role="admin")

        admin.set_password("admin123")

        db.session.add(admin)

        db.session.commit()


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):

            login_user(user)

            return redirect("/")

        return "Invalid login"

    return render_template("login.html")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect("/login")


# =========================
# ARREARS CALCULATION
# =========================
def calculate_arrears(loan):

    days_passed = (date.today() - loan.start_date).days

    if days_passed < 1:
        days_passed = 1

    expected_paid = loan.daily_payment * days_passed

    payments = Payment.query.filter_by(loan_id=loan.id).all()

    actual_paid = sum(p.amount for p in payments)

    arrears = expected_paid - actual_paid

    if arrears < 0:
        arrears = 0

    return expected_paid, actual_paid, arrears


# =========================
# DASHBOARD
# =========================
@app.route("/")
@login_required
def home():

    borrowers_count = Borrower.query.count()

    loans_count = Loan.query.count()

    payments = Payment.query.all()

    loans = Loan.query.all()

    total_portfolio = sum(l.total for l in loans)

    total_collected = sum(p.amount for p in payments)

    outstanding = total_portfolio - total_collected

    return render_template(
        "index.html",
        borrowers=borrowers_count,
        loans=loans_count,
        total_portfolio=total_portfolio,
        total_collected=total_collected,
        outstanding=outstanding
    )


# =========================
# ADD BORROWER
# =========================
@app.route("/add_borrower", methods=["GET", "POST"])
@login_required
def add_borrower():

    if request.method == "POST":

        borrower = Borrower(

            name=request.form["name"],

            phone=request.form["phone"],

            id_number=request.form["id_number"],

            officer_id=current_user.id
        )

        db.session.add(borrower)

        db.session.commit()

        return redirect("/borrowers")

    return render_template("borrower.html")


# =========================
# VIEW BORROWERS
# =========================
@app.route("/borrowers")
@login_required
def borrowers():

    if current_user.role == "admin":

        borrowers = Borrower.query.all()

    else:

        borrowers = Borrower.query.filter_by(officer_id=current_user.id).all()

    return render_template("borrowers.html", borrowers=borrowers)


# =========================
# ISSUE LOAN
# =========================
@app.route("/loan", methods=["GET", "POST"])
@login_required
def loan():

    if current_user.role == "admin":

        borrowers = Borrower.query.all()

    else:

        borrowers = Borrower.query.filter_by(officer_id=current_user.id).all()

    if request.method == "POST":

        borrower_id = int(request.form["borrower"])

        amount = float(request.form["amount"])

        interest = float(request.form["interest"])

        days = int(request.form["days"])

        total = amount + (amount * interest / 100)

        daily_payment = total / days

        loan = Loan(

            borrower_id=borrower_id,

            amount=amount,

            interest=interest,

            total=total,

            daily_payment=daily_payment,

            days=days,

            start_date=date.today()
        )

        db.session.add(loan)

        db.session.commit()

        return redirect("/borrowers")

    return render_template("loan.html", borrowers=borrowers)


# =========================
# RECORD PAYMENT
# =========================
@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():

    loans = Loan.query.all()

    if request.method == "POST":

        payment = Payment(

            loan_id=int(request.form["loan"]),

            amount=float(request.form["amount"])
        )

        db.session.add(payment)

        db.session.commit()

        return redirect("/borrowers")

    return render_template("payment.html", loans=loans)


# =========================
# BORROWER PROFILE
# =========================
@app.route("/borrower/<int:id>")
@login_required
def borrower_profile(id):

    borrower = Borrower.query.get_or_404(id)

    loans = Loan.query.filter_by(borrower_id=id).all()

    loan_data = []

    for loan in loans:

        expected, paid, arrears = calculate_arrears(loan)

        loan_data.append({
            "loan": loan,
            "expected": expected,
            "paid": paid,
            "arrears": arrears
        })

    return render_template(
        "borrower_profile.html",
        borrower=borrower,
        loan_data=loan_data
    )


# =========================
# MPESA CALLBACK (PLACEHOLDER)
# =========================
@app.route("/mpesa_callback", methods=["POST"])
def mpesa_callback():

    data = request.json

    print(data)

    return {"ResultCode": 0, "ResultDesc": "Success"}


# =========================
# RUN APP
# =========================
if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000, debug=True)