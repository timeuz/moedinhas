from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date, timedelta
import sqlite3
import schedule
import time

# Instanciar o objeto Flask
app = Flask(__name__)

# Configuração do banco de dados
DATABASE = 'tasks.db'

def create_database():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Cria a tabela 'tasks' se ainda não existir
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            user_name TEXT NOT NULL,
            fixed INTEGER NOT NULL,
            completed INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

create_database()

# Rota para a página de cadastro de tarefas
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        quem = request.form.get('quem')
        tarefa = request.form.get('tarefa')
        fixa = request.form.get('fixa')
        fixa = 1 if fixa else 0

        # Salvar a tarefa no banco de dados
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        c.execute('''
            INSERT INTO tasks (task_name, user_name, fixed, completed)
            VALUES (?, ?, ?, ?)
        ''', (tarefa, quem, fixa, 0))

        conn.commit()
        conn.close()

        return redirect(url_for('view_tasks'))

    return render_template('index.html')

# Rota para a página de visualização das tarefas
@app.route('/tasks')
def view_tasks():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Filtrar tarefas do Usuário 1
    c.execute('SELECT * FROM tasks WHERE user_name = ? AND ((completed != 1 AND date(created_at) = ?) OR (completed = 1 AND fixed = 1 AND completed != 1))', ('Valentina', date.today()))
    tasks_user1 = c.fetchall()

    # Filtrar tarefas do Usuário 2
    c.execute('SELECT * FROM tasks WHERE user_name = ? AND ((completed != 1 AND date(created_at) = ?) OR (completed = 1 AND fixed = 1 AND completed != 1))', ('Edgar', date.today()))
    tasks_user2 = c.fetchall()

    conn.close()

    return render_template('view_tasks.html', tasks_user1=tasks_user1, tasks_user2=tasks_user2)

# Rota para a página de relatório diário das tarefas
@app.route('/report/<username>')
def daily_report(username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        SELECT DATE(created_at) AS task_date, task_name
        FROM tasks
        WHERE user_name = ? AND completed = 1
        ORDER BY task_date DESC
    ''', (username,))

    tasks_completed = c.fetchall()
    conn.close()

    # Organizar as tarefas por dia
    daily_tasks = {}
    for task_date, task_name in tasks_completed:
        if task_date in daily_tasks:
            daily_tasks[task_date].append(task_name)
        else:
            daily_tasks[task_date] = [task_name]

    return render_template('daily_report.html', username=username, daily_tasks=daily_tasks)

# Rota para marcar tarefas como completadas
@app.route('/complete_task/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    # Atualizar o status da tarefa para concluída no banco de dados
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('view_tasks'))

# Atualização das tarefas fixas
def update_fixed_tasks():
    today = date.today()
    yesterday = today - timedelta(days=1)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('UPDATE tasks SET completed = 0 WHERE completed = 1 AND fixed = 1 AND date(created_at) = ?', (yesterday,))

    conn.commit()
    conn.close()

# Agendando a função para ser executada diariamente à meia-noite
schedule.every().day.at("00:00").do(update_fixed_tasks)

# Função para executar as tarefas agendadas em segundo plano
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # Iniciar a função de agendamento em segundo plano
    import threading
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)