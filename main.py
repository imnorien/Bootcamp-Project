import flet as ft
import pickle, pandas as pd, matplotlib.pyplot as plt, io, base64
import mysql.connector
from mysql.connector.errors import IntegrityError

# trained model
model = pickle.load(open("gold_model.pkl", "rb"))

def get_conn():
    return mysql.connector.connect(host="localhost", user="root", password="", database="db_gold_price")

def render_chart(prev, open_, avg7, pred):
    df = pd.DataFrame({"Metric": ['Previous', 'Open', '7-Day Avg', 'Predicted'],
                       "Value": [prev, open_, avg7, pred]})
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(df["Metric"], df["Value"], color=["gray", "blue", "green", "gold"])
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+5, f"{bar.get_height():.2f}", ha='center')
    ax.set_title("Price Comparison"); ax.set_ylabel("USD")
    ax.set_ylim(min(df["Value"])-50, max(df["Value"])+50)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    buf = io.BytesIO(); plt.tight_layout(); plt.savefig(buf, format="png"); plt.close(); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# Database
def insert_user(username, pw, fname, lname, email):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO accounts (username, password) VALUES (%s, %s)", (username, pw))
        aid = cur.lastrowid
        cur.execute("INSERT INTO users (account_id, first_name, last_name, email) VALUES (%s,%s,%s,%s)", (aid, fname, lname, email))
        conn.commit()
    except IntegrityError: raise ValueError("Username exists.")
    finally: cur.close(); conn.close()

def get_user(username, pw):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT account_id, username FROM accounts WHERE username=%s AND password=%s", (username, pw))
    res = cur.fetchone(); cur.close(); conn.close()
    return res

def save_prediction(aid, open_, prev, avg, pred, chart64):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO predictions (account_id, open_price, prev_price, avg_7, predicted_price, price_change, chart_base64)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (aid, open_, prev, avg, pred, open_ - prev, chart64))
    conn.commit(); cur.close(); conn.close()

# UI
def login_view(page):
    u = ft.TextField(label="Username")
    p = ft.TextField(label="Password", password=True, can_reveal_password=True)
    msg = ft.Text(color="red")

    def login(e):
        if not u.value.strip() or not p.value.strip():
            msg.value = "⚠️ Please enter both username and password."
        else:
            user = get_user(u.value.strip(), p.value.strip())
            if user:
                page.session.set("account_id", user[0])
                page.session.set("name", user[1])
                page.go("/predict")
                return
            else:
                msg.value = "❌ Invalid login."
        page.update()

    return ft.View("/login", scroll="auto", controls=[
        ft.Column([
            ft.Text("🔐 Login", size=24, weight="bold"),
            u, p,
            ft.ElevatedButton("Login", on_click=login),
            ft.TextButton("No account? Register", on_click=lambda _: page.go("/register")),
            msg
        ], horizontal_alignment="center")
    ])


def register_view(page):
    u = ft.TextField(label="Username")
    p = ft.TextField(label="Password", password=True, can_reveal_password=True)
    e = ft.TextField(label="Email")
    f = ft.TextField(label="First Name")
    l = ft.TextField(label="Last Name")
    msg = ft.Text(color="red")

    def register(e_):
        if not all([u.value.strip(), p.value.strip(), e.value.strip(), f.value.strip(), l.value.strip()]):
            msg.value = "⚠️ All fields are required."
        else:
            try:
                insert_user(u.value.strip(), p.value.strip(), f.value.strip(), l.value.strip(), e.value.strip())
                page.go("/login")
                return
            except ValueError as err:
                msg.value = f"❌ {err}"
        page.update()

    return ft.View("/register", scroll="auto", controls=[
        ft.Column([
            ft.Text("📝 Register", size=24, weight="bold"),
            u, p, e, f, l,
            ft.ElevatedButton("Register", on_click=register),
            ft.TextButton("Have an account? Login", on_click=lambda _: page.go("/login")),
            msg
        ], horizontal_alignment="center")
    ])

def predict_view(page):
    o, pr, avg = ft.TextField(label="Open Price", value="1800"), ft.TextField(label="Previous Price", value="1795"), ft.TextField(label="7-Day Avg", value="1798")
    diff, out, trend = ft.Text(), ft.Text(size=16, weight="bold", color="blue"), ft.Text(size=14, italic=True)
    img = ft.Image(width=500, height=300, visible=False)

    def predict(e):
        try:
            op, pp, av = float(o.value), float(pr.value), float(avg.value)
            pc = op - pp
            diff.value = f"🧮 Price Change: {pc:.2f} USD"

            pred = float(model.predict(pd.DataFrame([[op, pp, pc, av]], columns=["Open", "Prev_Price", "Price_Change", "7_day_avg"]))[0])
            out.value = f"💰 Predicted: ${pred:,.2f}"
            trend.value = f"{'📈 Price Increased' if pred > pp else '📉 Price Decreased' if pred < pp else '➖ Price No change'} by ${abs(pred - pp):.2f}"

            c64 = render_chart(float(pp), float(op), float(av), float(pred))
            img.src_base64, img.visible = c64, True

            save_prediction(int(page.session.get("account_id")), float(op), float(pp), float(av), float(pred), c64)

        except Exception as ex:
            out.value, trend.value, img.visible = "❌ Error", str(ex), False
        page.update()


    return ft.View("/predict", scroll="auto", controls=[
        ft.Column([
            ft.Text("🟡 Gold Price Prediction", size=24, weight="bold"),
            ft.Text("Enter financial indicators to predict today's gold price.", size=14),
                ft.Container(
                    content=ft.Text(f"Welcome, {page.session.get('name') or 'Guest'}!", size=20),
                    alignment=ft.alignment.center_left
                ),
            o, pr, avg,
            ft.ElevatedButton("📊 Predict", on_click=predict),
            diff, out, trend, img,
            ft.TextButton("Logout", on_click=lambda _: page.go("/login"))
        ], horizontal_alignment="center")
    ])

# main
def main(page: ft.Page):
    def route_change(e):
        page.views.clear()
        if page.route == "/predict" and page.session.get("account_id"):
            page.views.append(predict_view(page))
        elif page.route == "/register":
            page.views.append(register_view(page))
        else:
            page.views.append(login_view(page))
        page.update()

    page.on_route_change = route_change
    page.go("/login")

ft.app(target=main)
