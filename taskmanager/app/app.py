from flask import Flask, request, jsonify
import os
import time
import psycopg2


app = Flask(__name__)

# Open a PostgreSQL connection.
def get_connection():
    return psycopg2.connect(    # Read database settings from the environment.
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )

# Create the tasks table at startup if it does not exist.
def init_db():
    # Retry while PostgreSQL finishes starting; Compose only orders container startup.
    for _ in range(20):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL
                )
                """
            )
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception:
            time.sleep(2)




# Return all tasks as JSON.
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM tasks ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()


    tasks = []
    for row in rows:
        tasks.append({"id": row[0], "title": row[1]})


    return jsonify(tasks)




# Save a new task from the JSON request.
@app.route("/api/tasks", methods=["POST"])
def add_task():
    data = request.get_json()
    title = data.get("title", "").strip()


    if not title:
        return jsonify({"error": "Title is required"}), 400


    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (title) VALUES (%s)", (title,))
    conn.commit()
    cur.close()
    conn.close()


    return jsonify({"status": "ok"}), 201




# Delete a task by ID.
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    cur.close()
    conn.close()


    return jsonify({"status": "deleted"})




if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=6000)
