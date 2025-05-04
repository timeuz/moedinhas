import os
import logging
import json
from collections import defaultdict
from flask import Flask, render_template, redirect, url_for, session, request, flash
from models import db, Usuario, Tarefa, Premio, Resgate
from functools import wraps
from datetime import timedelta, datetime
from pywebpush import webpush, WebPushException

# app = Flask(__name__)
app = Flask(__name__, static_folder=".")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/service-worker.js")
def sw():
    return app.send_static_file("service-worker.js")


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///moedinhas.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.urandom(24).hex()
app.permanent_session_lifetime = timedelta(hours=1)

db.init_app(app)


# Decoradores para controle de acesso
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def pais_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("usuario_tipo") != "responsavel":
            flash("Acesso restrito a responsáveis.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


# ROTAS


@app.route("/")
@login_required
def index():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    if session.get("usuario_tipo") == "responsavel":
        return redirect(url_for("painel_pais"))
    else:
        return redirect(url_for("painel_filho"))


@app.route("/tarefas")
@login_required
def tarefas():
    tipo = session.get("usuario_tipo")
    usuario_id = session.get("usuario_id")

    if tipo == "filho":
        # Filho só vê suas próprias tarefas pendentes
        tarefas = Tarefa.query.filter_by(usuario_id=usuario_id, feita=False).all()
        return render_template(
            "tarefas.html", tarefas=tarefas, VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY
        )

    # Responsável vê todas as tarefas pendentes, separadas por filho
    filhos = Usuario.query.filter_by(tipo="filho").all()
    tarefas_por_filho = {
        filho.nome: Tarefa.query.filter_by(usuario_id=filho.id, feita=False).all()
        for filho in filhos
    }

    return render_template(
        "tarefas.html",
        tarefas_por_filho=tarefas_por_filho,
        tipo="responsavel",
        VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY,
    )


@app.route("/concluir/<int:id>")
def concluir(id):
    tarefa = Tarefa.query.get_or_404(id)
    tarefa.feita = True
    tarefa.data_conclusao = datetime.utcnow()
    usuario = Usuario.query.get(tarefa.usuario_id)
    usuario.moedas += tarefa.valor_moeda
    db.session.commit()
    return redirect(url_for("tarefas"))


@app.route("/relatorio")
@pais_required
def relatorio():
    mes = request.args.get("mes", type=int)
    ano = request.args.get("ano", type=int)

    agora = datetime.utcnow()
    mes = mes or agora.month
    ano = ano or agora.year

    filhos = Usuario.query.filter_by(tipo="filho").all()
    relatorios = []

    for filho in filhos:
        tarefas_concluidas = Tarefa.query.filter(
            Tarefa.usuario_id == filho.id,
            Tarefa.feita == True,
            db.extract("month", Tarefa.data_conclusao) == mes,
            db.extract("year", Tarefa.data_conclusao) == ano,
        ).count()

        moedas_ganhas = (
            db.session.query(db.func.sum(Tarefa.valor_moeda))
            .filter(
                Tarefa.usuario_id == filho.id,
                Tarefa.feita == True,
                db.extract("month", Tarefa.data_conclusao) == mes,
                db.extract("year", Tarefa.data_conclusao) == ano,
            )
            .scalar()
            or 0
        )

        resgates_aprovados = Resgate.query.filter(
            Resgate.usuario_id == filho.id,
            Resgate.status == "aprovado",
            db.extract("month", Resgate.data) == mes,
            db.extract("year", Resgate.data) == ano,
        ).count()

        moedas_gastas = (
            db.session.query(db.func.sum(Premio.custo))
            .join(Resgate)
            .filter(
                Resgate.usuario_id == filho.id,
                Resgate.status == "aprovado",
                db.extract("month", Resgate.data) == mes,
                db.extract("year", Resgate.data) == ano,
            )
            .scalar()
            or 0
        )

        tarefas_detalhadas = (
            Tarefa.query.filter(
                Tarefa.usuario_id == filho.id,
                Tarefa.feita == True,
                db.extract("month", Tarefa.data_conclusao) == mes,
                db.extract("year", Tarefa.data_conclusao) == ano,
            )
            .order_by(Tarefa.data_conclusao)
            .all()
        )

        tarefas_por_dia = defaultdict(list)
        for tarefa in tarefas_detalhadas:
            dia = tarefa.data_conclusao.strftime("%d/%m/%Y")
            tarefas_por_dia[dia].append(
                {"descricao": tarefa.descricao, "valor": tarefa.valor_moeda}
            )

        relatorios.append(
            {
                "nome": filho.nome,
                "tarefas": tarefas_concluidas,
                "ganhas": moedas_ganhas,
                "resgates": resgates_aprovados,
                "gastas": moedas_gastas,
                "detalhes": dict(
                    tarefas_por_dia
                ),  # convertendo de defaultdict para dict
            }
        )

    return render_template("relatorio.html", relatorios=relatorios, mes=mes, ano=ano)


@app.route("/loja")
@login_required
def loja():
    premios = Premio.query.all()
    return render_template("loja.html", premios=premios)


@app.route("/cadastro_premio", methods=["GET", "POST"])
@pais_required
def cadastro_premio():
    if request.method == "POST":
        nome = request.form["nome"]
        custo = int(request.form["custo"])

        if Premio.query.filter_by(nome=nome).first():
            flash("Já existe um prêmio com esse nome.", "danger")
        else:
            novo = Premio(nome=nome, custo=custo)
            db.session.add(novo)
            db.session.commit()
            atualizar_sessao_premios()
            flash("Prêmio cadastrado com sucesso!", "success")
            return redirect(url_for("painel_pais"))

    return render_template("cadastro_premio.html")


@app.route("/gerenciar_premios")
@pais_required
def gerenciar_premios():
    premios = Premio.query.all()
    return render_template("gerenciar_premios.html", premios=premios)


@app.route("/editar_premio/<int:id>", methods=["GET", "POST"])
@pais_required
def editar_premio(id):
    premio = Premio.query.get_or_404(id)

    if request.method == "POST":
        premio.nome = request.form["nome"]
        premio.custo = int(request.form["custo"])
        db.session.commit()
        atualizar_sessao_premios()
        flash("Prêmio atualizado com sucesso!", "success")
        return redirect(url_for("gerenciar_premios"))

    return render_template("editar_premio.html", premio=premio)


@app.route("/excluir_premio/<int:id>")
@pais_required
def excluir_premio(id):
    premio = Premio.query.get_or_404(id)
    db.session.delete(premio)
    db.session.commit()
    atualizar_sessao_premios()
    flash("Prêmio excluído com sucesso.", "info")
    return redirect(url_for("gerenciar_premios"))


@app.route("/resgatar/<int:id>")
@login_required
def resgatar(id):
    premio = Premio.query.get_or_404(id)
    usuario = Usuario.query.get(session["usuario_id"])

    if usuario.tipo != "filho":
        flash("Somente filhos podem solicitar prêmios.", "danger")
        return redirect(url_for("loja"))

    if usuario.moedas >= premio.custo:
        # Apenas cria um resgate pendente
        novo_resgate = Resgate(
            usuario_id=usuario.id, premio_id=premio.id, status="pendente"
        )
        db.session.add(novo_resgate)
        db.session.commit()
        flash("Solicitação enviada! Aguarde a aprovação.", "info")
    else:
        flash("Você não tem moedinhas suficientes.", "warning")

    return redirect(url_for("loja"))


@app.route("/resgates")
@login_required
def resgates():
    tipo = session.get("usuario_tipo")
    usuario_id = session.get("usuario_id")

    if tipo == "filho":
        resgates = (
            Resgate.query.filter_by(usuario_id=usuario_id)
            .order_by(Resgate.data.desc())
            .all()
        )
    else:
        resgates = Resgate.query.order_by(Resgate.data.desc()).all()

    return render_template("resgates_historico.html", resgates=resgates)


@app.route("/resgates_pendentes")
@pais_required
def resgates_pendentes():
    pendentes = Resgate.query.filter_by(status="pendente").all()
    return render_template(
        "resgates_pendentes.html",
        pendentes=pendentes,
        VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY,
    )


@app.route("/aprovar/<int:id>")
@pais_required
def aprovar(id):
    resgate = Resgate.query.get_or_404(id)
    usuario = Usuario.query.get(resgate.usuario_id)
    premio = Premio.query.get(resgate.premio_id)

    if usuario.moedas >= premio.custo:
        usuario.moedas -= premio.custo
        resgate.status = "aprovado"
        db.session.commit()
        flash("Resgate aprovado!", "success")
        enviar_notificacao(
            usuario.id,
            "🎉 Resgate aprovado!",
            f"Seu pedido de '{premio.nome}' foi aprovado!",
        )
    else:
        flash("Usuário não tem mais moedinhas suficientes.", "danger")

    return redirect(url_for("resgates_pendentes"))


@app.route("/recusar/<int:id>")
@pais_required
def recusar(id):
    resgate = Resgate.query.get_or_404(id)
    usuario = Usuario.query.get(resgate.usuario_id)
    premio = Premio.query.get(resgate.premio_id)
    resgate.status = "recusado"
    db.session.commit()
    flash("Resgate recusado.", "secondary")
    enviar_notificacao(
        usuario.id,
        "❌ Resgate recusado",
        f"Seu pedido de '{premio.nome}' foi recusado.",
    )
    return redirect(url_for("resgates_pendentes"))


@app.route("/login", methods=["GET", "POST"])
def login():
    session.permanent = True
    session["tem_premios"] = Premio.query.count() > 0
    if request.method == "POST":
        nome = request.form["nome"]
        senha = request.form["senha"]
        user = Usuario.query.filter_by(nome=nome, senha=senha).first()
        if user:
            session["usuario_id"] = user.id
            session["usuario_tipo"] = user.tipo
            if user.tipo == "responsavel":
                return redirect(url_for("painel_pais"))
            else:
                return redirect(url_for("painel_filho"))
        else:
            flash("Nome ou senha inválidos", "danger")
    return render_template("login.html")


def atualizar_sessao_premios():
    session["tem_premios"] = Premio.query.count() > 0


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu com sucesso.", "success")
    return redirect(url_for("login"))


@app.route("/painel_pais")
@pais_required
def painel_pais():
    usuarios = Usuario.query.all()
    return render_template("painel_pais.html", usuarios=usuarios)


@app.route("/painel_filho")
@login_required
def painel_filho():
    usuario = Usuario.query.get(session["usuario_id"])
    tem_premios = Premio.query.count() > 0
    return render_template(
        "painel_filho.html",
        usuario=usuario,
        tem_premios=tem_premios,
        VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY,
    )


@app.route("/cadastro_usuario", methods=["GET", "POST"])
@pais_required
def cadastro_usuario():
    if request.method == "POST":
        nome = request.form["nome"]
        senha = request.form["senha"]
        tipo = request.form["tipo"]

        # Verifica se já existe
        if Usuario.query.filter_by(nome=nome).first():
            flash("Já existe um usuário com esse nome.", "danger")
        else:
            novo = Usuario(nome=nome, senha=senha, tipo=tipo, moedas=0)
            db.session.add(novo)
            db.session.commit()
            flash(f"{tipo.capitalize()} cadastrado com sucesso!", "success")
            return redirect(url_for("painel_pais"))

    return render_template("cadastro_usuario.html")


@app.route("/usuarios")
@pais_required
def usuarios():
    lista = Usuario.query.all()
    return render_template("usuarios.html", usuarios=lista)


@app.route("/mudar_senha/<int:id>", methods=["GET", "POST"])
@pais_required
def mudar_senha_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == "POST":
        nova = request.form["nova_senha"]
        confirmar = request.form["confirmar_senha"]

        if nova != confirmar:
            flash("A nova senha e a confirmação não coincidem.", "warning")
        else:
            usuario.senha = nova
            db.session.commit()
            flash(f"Senha de {usuario.nome} atualizada com sucesso!", "success")
            return redirect(url_for("usuarios"))

    return render_template("mudar_senha_usuario.html", usuario=usuario)


@app.route("/cadastrar_tarefa", methods=["GET", "POST"])
@pais_required
def cadastrar_tarefa():
    filhos = Usuario.query.filter_by(tipo="filho").all()

    if request.method == "POST":
        descricao = request.form["descricao"]
        valor = int(request.form["valor_moeda"])
        usuario_id = int(request.form["filho_id"])
        recorrente = "recorrente" in request.form

        nova = Tarefa(
            descricao=descricao,
            valor_moeda=valor,
            usuario_id=usuario_id,
            recorrente=recorrente,
        )
        db.session.add(nova)
        db.session.commit()

        atualizar_sessao_premios()  # opcional
        flash("Tarefa cadastrada com sucesso!", "success")

        # ✅ Enviar notificação para o filho
        filho = Usuario.query.get(usuario_id)
        enviar_notificacao(
            usuario_id,
            "📋 Nova Tarefa!",
            f"{filho.nome}, você tem uma nova tarefa para completar!",
        )

        return redirect(url_for("painel_pais"))

    return render_template(
        "cadastrar_tarefa.html", filhos=filhos, VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY
    )


@app.route("/renovar_tarefas")
@pais_required
def renovar_tarefas():
    tarefas = Tarefa.query.filter_by(recorrente=True, feita=True).all()
    novas = []
    for tarefa in tarefas:
        nova = Tarefa(
            descricao=tarefa.descricao,
            valor_moeda=tarefa.valor_moeda,
            usuario_id=tarefa.usuario_id,
            recorrente=True,
        )
        novas.append(nova)

    if novas:
        db.session.add_all(novas)
        db.session.commit()
        flash(f"{len(novas)} tarefas renovadas com sucesso!", "success")
        enviar_notificacao(
            tarefa.usuario_id,
            "🔁 Tarefas renovadas",
            f"Você tem novas tarefas disponíveis hoje!",
        )
    else:
        flash("Nenhuma tarefa recorrente para renovar.", "info")

    return redirect(url_for("painel_pais"))


@app.route("/excluir_tarefa/<int:id>")
@pais_required
def excluir_tarefa(id):
    tarefa = Tarefa.query.get_or_404(id)
    db.session.delete(tarefa)
    db.session.commit()
    flash("Tarefa excluída com sucesso.", "info")
    return redirect(url_for("tarefas"))


VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_CLAIMS = {"sub": os.getenv("VAPID_CLAIMS_SUB", "mailto:default@email.com")}


assinaturas = {}  # salvar em banco depois


@app.route("/salvar_assinatura", methods=["POST"])
def salvar_assinatura():
    data = request.get_json()
    usuario_id = session.get("usuario_id")
    if usuario_id:
        assinaturas[usuario_id] = data
        logger.info(f"Assinatura salva para usuário {usuario_id}")
        return "", 204
    logger.warning("Tentativa de salvar assinatura sem usuário logado")
    return "", 400


def enviar_notificacao(usuario_id, titulo, corpo):
    sub = assinaturas.get(usuario_id)
    if not sub:
        logger.warning(
            f"Sem assinatura para usuário {usuario_id}; notificação não enviada"
        )
        return

    try:
        resp = webpush(
            subscription_info=sub,
            data=json.dumps({"title": titulo, "body": corpo}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        logger.info(f"Push enviado para {usuario_id}, status {resp.status_code}")
    except WebPushException as ex:
        logger.error(f"Falha ao enviar push para {usuario_id}: {ex}")
    except Exception as ex:
        logger.exception(f"Erro inesperado ao enviar push para {usuario_id}")


@app.route("/test_push")
@login_required
def test_push():
    uid = session["usuario_id"]
    enviar_notificacao(
        uid, "🚀 Teste de Notificação", "Se você vê isto, o envio funcionou!"
    )
    return "", 204


# POPULAR BANCO


@app.cli.command("criar")
def criar():
    db.drop_all()
    db.create_all()
    u1 = Usuario(nome="admin", senha="q1w2e3R$", tipo="responsavel")
    db.session.add_all([u1])
    # tarefas = [
    #     Tarefa(descricao="Arrumar a cama", valor_moeda=5, usuario_id=1),
    #     Tarefa(descricao="Guardar os brinquedos", valor_moeda=3, usuario_id=1),
    # ]
    # premios = [
    #     Premio(nome="Cartão Roblox R$10", custo=50),
    #     Premio(nome="Tempo extra no videogame", custo=30),
    # ]
    # db.session.add_all(tarefas + premios)
    db.session.commit()
    print("✅ Banco populado com dados iniciais.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5123, debug=True)
