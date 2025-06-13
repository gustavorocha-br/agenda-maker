from flask import Flask, render_template, jsonify, session, request
from flask_sqlalchemy import SQLAlchemy
import uuid
import datetime

app = Flask(__name__)

db = SQLAlchemy(app)

# Banco de dados
class Professor(db.Model):
    id = db.Column(db.String(), primary_key=True)
    nome = db.Column(db.String())
    email = db.Column(db.String())
    senha = db.Column(db.String())

    def __init__(self, id, nome, email, senha):
        self.id = id
        self.nome = nome 
        self.email = email
        self.senha = senha

class Agendamento(db.Model):
    id = db.Column(db.String(), primary_key=True)
    horario = db.Column(db.String())
    horaInicio = db.Column(db.DateTime)
    horaTermino = db.Column(db.DateTime)
    professor = db.Column(db.String())
    dia = db.Column(db.DateTime)
    
    def __init__(self, id, horario, horaInicio, horaTermino, professor, dia):
        self.id = id 
        self.horario = horario
        self.horaInicio = horaInicio
        self.horaTermino = horaTermino 
        self.professor = professor 
        self.dia = dia

@app.route("/")
def homepage():
    try:
        prof = session["prof"]
        return render_template("index.html")
    except Exception as e:
        return print(e)

@app.route("/api/cadastra-professor", methods=["POST"])
def cadastraProfessor():
    try:
        nome = request.form.get("prof-nome")
        email = request.form.get("prof-email")
        senha = request.form.get("prof-senha")

        newProf = Professor(id=str(uuid.uuid4()), nome=nome, email=email, senha=senha)
        db.session.add(newProf)
        db.session.commit()

        return jsonify({
            "msg": "success",
            "details": "Professor cadastrado com sucesso!"
        })
    except Exception as e:
        return jsonify({
            "msg": "error",
            "details": str(e)
        })

@app.route("/api/agenda-sala", methods=["POST"])
def agendaSala():
    try:
        professor = session["prof"]
        opcao = request.form.get("opcao-agendamento")
        data = datetime.datetime.now().date()

        horaTermino = None
        horaInicio = None

        if opcao == "opcao1":
            horaInicio = "08:00"
            horaTermino = "10:00"
        if opcao == "opcao2":
            horaInicio = "10:00"
            horaTermino = "12:00"
        if opcao == "opcao3":
            horaInicio = "13:30"
            horaTermino = "15:00"
        if opcao == "opcao4":
            horaInicio = "15:00"
            horaTermino = "17:00"

        newAgendamento = Agendamento(id=str(uuid.uuid4()), 
                                    horario=opcao, horaInicio=horaInicio, 
                                    horaTermino=horaTermino, professor=professor,
                                    dia=data)

        db.session.add(newAgendamento)
        db.session.commit()

        return jsonify({
            "msg": "success",
            "details": "Agendamento concluído"
        })
    except Exception as e:
        return jsonify({
            "msg": "error",
            "details:": str(e)
        })
    
@app.route("/api/cancelar-agendamento/<id>")
def cancelarAgendamento(id):
    try:
        agendamento = Agendamento.query.filter_by(id=id).first()
        db.session.delete(agendamento)
        db.session.commit()

        return jsonify({
            "msg": "success",
            "details": "Agendamento cancelado"
        })
    except Exception as e:
        return jsonify({
            "msg": "error":
            "details": str(e)
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)