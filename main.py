import pandas as pd
import datetime
import calendar
import json

hoje = datetime.date.today()
qtd_dias = calendar.monthrange(hoje.year, hoje.month)[1]
df_digao = pd.read_excel('data.xlsx', sheet_name = "digao", skipfooter=qtd_dias-hoje.day)
df_farofas = pd.read_excel('data.xlsx', sheet_name = "farofas")

dict_teste={}
for indice,dado in df_digao.iterrows():
    # dict_teste=name[1].to_dict()
    if dado["DIA"] == 6:
        dict_teste=dict(dado)

print(dict_teste["DIA"])