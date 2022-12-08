from flask import Flask, render_template
import pandas as pd
import datetime
import calendar

hoje = datetime.date.today()
qtd_dias = calendar.monthrange(hoje.year, hoje.month)[1]
df_digao = pd.read_excel('data.xlsx', sheet_name = "digao", skipfooter=qtd_dias-hoje.day)
df_farofas = pd.read_excel('data.xlsx', sheet_name = "farofas", skipfooter=qtd_dias-hoje.day)

for indice,dado in df_digao.iterrows():
    if dado["DIA"] == hoje.day:
        dict_info=dict(dado)

app = Flask(__name__, static_url_path='/static')

@app.route('/')
def index():
    return render_template('index.html', data=dict_info)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)