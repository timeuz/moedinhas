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
        dict_digao_hoje=dict(dado)

dict_digao=df_digao.to_dict()

dict_info_full={}
items_digao={"COCOS":'',"THOMAS":'',"JANELA":'',"LIXO":'',"BANHO":'',"CAFE":'',"MESA":'',"ROUPAS":''}

# Cria dict com dias do mês baseado nos dias que ja passaram do mês corrente
dicts = {}
for i in range(31):
    dicts[i] = i+1

# Cria dict com tarefas de digao para cada dia do mês corrente que já passou
for i in dicts.items():
    if i[1] <= len(dicts):
        dict_info_full[i[1]] = items_digao
    else:
        break
# print("********************")
# print("******* HOJE *******")
# print("********************")
# print(dict_digao_hoje)
# print("********************")
# print("******* FULL *******")
# print("********************")
for i in range(1,32):
    for indice,dado in df_digao.iterrows():
        dict_info_full[i]['COCOS']="X" # pegar o que foi lido no df_digao e popular o dict_info_full

print(dict_info_full)

app = Flask(__name__, static_url_path='/static')

@app.route('/')
def index():
    return render_template('index.html',
                           data=dict_digao_hoje,
                           df_digao=dict_info_full
                          )


# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080)