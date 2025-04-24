from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True)
    senha = db.Column(db.String(100))
    tipo = db.Column(db.String(10))  # 'filho' ou 'responsavel'
    moedas = db.Column(db.Integer, default=0)


class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100))
    valor_moeda = db.Column(db.Integer)
    feita = db.Column(db.Boolean, default=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    recorrente = db.Column(db.Boolean, default=False)
    data_conclusao = db.Column(db.DateTime)


class Premio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    custo = db.Column(db.Integer)


class Resgate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    premio_id = db.Column(db.Integer, db.ForeignKey("premio.id"))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(
        db.String(20), default="pendente"
    )  # pendente, aprovado, recusado
