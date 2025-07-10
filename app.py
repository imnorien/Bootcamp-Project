import flet as ft
import pickle
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import mysql.connector
from mysql.connector.errors import IntegrityError

# Load model
with open("gold_model.pkl", "rb") as f:
    model = pickle.load(f)

# Chart renderer
def render_chart(prev_price, open_price, avg_7, prediction):
    data = {
        'Metric': ['Previous Price', 'Open Price', '7-Day Avg', 'Predicted Price'],
        'Value': [prev_price, open_price, avg_7, prediction]
    }
    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(df['Metric'], df['Value'], color=['#6c757d', '#0d6efd', '#20c997', '#ffc107'])

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + 5, f'{yval:.2f}', ha='center')

    ax.set_title("Inputs vs Predicted Price")
    ax.set_ylabel("USD")
    ax.set_ylim(min(df['Value']) - 50, max(df['Value']) + 50)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# Database connection
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_gold_price"
    )

# Insert account and user
def insert_account_and_user(username, password, first_name, last_name, email):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO accounts (username, password) VALUES (%s, %s)", (username, password))
        account_id = cursor.lastrowid
        cursor.execute("INSERT INTO users (account_id, first_name, last_name, email) VALUES (%s, %s, %s, %s)",
                       (account_id, first_name, last_name, email))
        conn.commit()
    except IntegrityError:
        raise ValueError("Username already exists.")
    finally:
        cursor.close()
        conn.close()

# Get account info
def get_account(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT account_id, username FROM accounts WHERE username = %s AND password = %s",
                   (username, password))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

# Insert prediction
def insert_prediction(account_id, open_price, prev_price, avg_7, prediction, chart_base64):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO predictions (account_id, open_price, prev_price, avg_7, predicted_price, price_change, chart_base64)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (account_id, open_price, prev_price, avg_7, prediction, open_price - prev_price, chart_base64))
    conn.commit()
    cursor.close()
    conn.close()

# Login UI
def login_view(page):
    username = ft.TextField(label="Username")
    password = ft.TextField(label="Password", password=True, can_reveal_password=True)
    info_text = ft.Text(color=ft.Colors.RED)

    def login_click(e):
        account = get_account(username.value, password.value)
        if account:
            page.session.set("account_id", account[0])
            page.session.set("name", account[1])
            page.go("/predict")
        else:
            info_text.value = "❌ Invalid login."
            page.update()

    return ft.View(
        "/login",
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Column([
                ft.Text("🔐 Login", size=24, weight="bold"),
                username, password,
                ft.ElevatedButton("Login", on_click=login_click),
                ft.TextButton("Don't have an account? Register here", on_click=lambda _: page.go("/register")),
                info_text
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ]
    )

# Register UI
def register_view(page):
    username = ft.TextField(label="Username")
    password = ft.TextField(label="Password", password=True, can_reveal_password=True)
    email = ft.TextField(label="Email")
    first_name = ft.TextField(label="First Name")
    last_name = ft.TextField(label="Last Name")
    info_text = ft.Text(color=ft.Colors.RED)

    def register_click(e):
        try:
            insert_account_and_user(username.value, password.value, first_name.value, last_name.value, email.value)
            page.go("/login")
        except ValueError as ve:
            info_text.value = f"❌ {ve}"
            page.update()

    return ft.View(
        "/register",
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Column([
                ft.Text("📝 Register", size=24, weight="bold"),
                username, password, email, first_name, last_name,
                ft.ElevatedButton("Register", on_click=register_click),
                ft.TextButton("Already have an account? Login here", on_click=lambda _: page.go("/login")),
                info_text
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ]
    )

# Prediction UI
def prediction_view(page):
    open_input = ft.TextField(label="Open Price (USD)", value="1800")
    prev_input = ft.TextField(label="Previous Day's Price (USD)", value="1795")
    avg7_input = ft.TextField(label="7-Day Moving Avg (USD)", value="1798")

    price_change_text = ft.Text()
    result_text = ft.Text(size=16, weight="bold", color=ft.Colors.PRIMARY)
    trend_text = ft.Text(size=14, italic=True)
    chart_image = ft.Image(width=500, height=300, visible=False)

    def predict_click(e):
        try:
            open_price = float(open_input.value)
            prev_price = float(prev_input.value)
            avg_7 = float(avg7_input.value)
            price_change = open_price - prev_price

            price_change_text.value = f"🧮 Calculated Price Change: {price_change:.2f} USD"

            input_df = pd.DataFrame([[open_price, prev_price, price_change, avg_7]],
                                    columns=['Open', 'Prev_Price', 'Price_Change', '7_day_avg'])
            prediction = float(model.predict(input_df)[0])
            result_text.value = f"💰 Predicted Gold Price: ${prediction:,.2f}"

            if prediction > prev_price:
                trend_text.value = f"📈 Price increased by ${prediction - prev_price:.2f} from yesterday."
            elif prediction < prev_price:
                trend_text.value = f"📉 Price decreased by ${prev_price - prediction:.2f} from yesterday."
            else:
                trend_text.value = "➖ No change from the previous day's price."

            chart_base64 = render_chart(prev_price, open_price, avg_7, prediction)
            chart_image.src_base64 = chart_base64
            chart_image.visible = True

            insert_prediction(
                int(page.session.get("account_id")),
                open_price,
                prev_price,
                avg_7,
                prediction,
                chart_base64
            )

        except Exception as ex:
            result_text.value = "❌ Error: Invalid input."
            trend_text.value = str(ex)
            chart_image.visible = False

        page.update()

    return ft.View(
        "/predict",
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Column([
                ft.Text("🟡 Gold Price Prediction", size=24, weight="bold", text_align="center"),
                ft.Text("Enter financial indicators to predict today's gold price.", size=14),
                ft.Container(
                    content=ft.Text(f"Welcome, {page.session.get('name') or 'Guest'}!", size=20),
                    alignment=ft.alignment.center_left
                ),
                ft.ResponsiveRow([
                    ft.Container(open_input, col={"xs": 12, "md": 4}),
                    ft.Container(prev_input, col={"xs": 12, "md": 4}),
                    ft.Container(avg7_input, col={"xs": 12, "md": 4}),
                ], run_spacing=10),
                ft.ElevatedButton("📊 Predict", on_click=predict_click),
                price_change_text, result_text, trend_text, chart_image,
                ft.TextButton("Logout", on_click=lambda _: page.go("/login"))
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ]
    )

# Routing
def main(page: ft.Page):
    def route_change(e):
        page.views.clear()
        if page.route == "/predict" and page.session.get("account_id"):
            page.views.append(prediction_view(page))
        elif page.route == "/register":
            page.views.append(register_view(page))
        else:
            page.views.append(login_view(page))
        page.update()

    page.on_route_change = route_change
    page.go("/login")

ft.app(target=main)
