import os
import uuid
import datetime
from functools import wraps

from flask import Flask, render_template, jsonify, session, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pytz # Para manipulação de fuso horário mais robusta

# --- Configuração da Aplicação Flask ---
app = Flask(__name__)

# Configurações do Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.rssmqiuinfplvzdusnzq:incorreta@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurações de Sessão
# ATENÇÃO: Em produção, use uma SECRET_KEY forte e gerada aleatoriamente.
# Recomendação: Gerar com os.urandom(24) ou secrets.token_hex(16)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma_chave_secreta_muito_mais_forte_e_aleatoria_aqui_para_desenvolvimento')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=14)

db = SQLAlchemy(app)

# Define o fuso horário de Brasília
BRASILIA_TZ = pytz.timezone('America/Sao_Paulo')

# --- Modelos do Banco de Dados ---
class Professor(db.Model):
    __tablename__ = 'professores' # Define o nome da tabela
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())) # UUID com tamanho fixo
    nome = db.Column(db.String(100), nullable=False) # Adicionado nullable=False
    email = db.Column(db.String(120), unique=True, nullable=False) # Email único
    senha_hash = db.Column(db.String(255), nullable=False) # Armazena o hash da senha

    def __init__(self, nome, email, senha):
        self.nome = nome
        self.email = email
        self.set_password(senha) # Usa método para setar a senha

    def set_password(self, senha):
        """Gera o hash da senha."""
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        """Verifica se a senha fornecida corresponde ao hash."""
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        """Converte o objeto Professor para um dicionário."""
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email
        }

    def __repr__(self):
        return f'<Professor {self.nome}>'

class Agendamento(db.Model):
    __tablename__ = 'agendamentos' # Define o nome da tabela
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())) # UUID com tamanho fixo
    # 'tipo' pode ser 'aula', 'reuniao', 'evento' etc. Para maior flexibilidade.
    tipo = db.Column(db.String(50), nullable=False) 
    hora_inicio = db.Column(db.DateTime, nullable=False)
    hora_termino = db.Column(db.DateTime, nullable=False)
    professor_id = db.Column(db.String(36), db.ForeignKey('professores.id'), nullable=False) # Chave estrangeira
    dia = db.Column(db.Date, nullable=False) # Usar Date se for apenas o dia
    
    # Relação com a tabela Professor
    professor = db.relationship('Professor', backref='agendamentos')

    def __init__(self, tipo, hora_inicio, hora_termino, professor_id, dia):
        self.tipo = tipo
        self.hora_inicio = hora_inicio
        self.hora_termino = hora_termino
        self.professor_id = professor_id
        self.dia = dia

    def to_dict(self):
        """Converte o objeto Agendamento para um dicionário."""
        hora_inicio_br = self.hora_inicio.astimezone(BRASILIA_TZ)
        hora_termino_br = self.hora_termino.astimezone(BRASILIA_TZ)
        return {
            "id": self.id,
            "tipo": self.tipo,
            "hora_inicio": hora_inicio_br.isoformat(),
            "hora_termino": hora_termino_br.isoformat(),
            "dia": self.dia.isoformat(),
            "professor_id": self.professor_id,
            "professor_nome": self.professor.nome
        }

    def __repr__(self):
        return f'<Agendamento {self.tipo} por {self.professor.nome} em {self.dia.strftime("%Y-%m-%d")} das {self.hora_inicio.strftime("%H:%M")} às {self.hora_termino.strftime("%H:%M")}>'

# --- Funções Auxiliares ---
def get_current_datetime_br():
    """Retorna a data e hora atual no fuso horário de Brasília."""
    return datetime.datetime.now(BRASILIA_TZ)

def auth_required(f):
    """Decorador para proteger rotas que exigem autenticação."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'prof_id' not in session:
            app.logger.warning("Tentativa de acesso não autorizado a uma rota protegida.")
            return jsonify({"msg": "error", "details": "Acesso não autorizado. Faça login primeiro."}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas da Aplicação ---
@app.route("/")
def homepage():
    """Rota da página inicial que renderiza o HTML."""
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    """Rota de status da API para verificar se está funcionando."""
    try:
        current_time = get_current_datetime_br()
        app.logger.info(f"Hora atual no servidor (Brasília): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return jsonify({"message": "Bem-vindo à API de Agendamento!", "status": "online", "current_time": current_time.isoformat()}), 200
    except Exception as e:
        app.logger.error(f"Erro na rota /api/status: {e}")
        return jsonify({"msg": "error", "details": "Erro interno do servidor."}), 500

@app.route("/api/cadastra-professor", methods=["POST"])
def cadastra_professor():
    """Endpoint para cadastrar um novo professor."""
    try:
        

        nome = request.form.get("prof-nome")
        email = request.form.get("prof-email")
        senha = request.form.get("prof-senha")

        if not all([nome, email, senha]):
            return jsonify({"msg": "error", "details": "Nome, email e senha são obrigatórios."}), 400
        
        # Validação básica de email
        if "@" not in email or "." not in email:
            return jsonify({"msg": "error", "details": "Formato de e-mail inválido."}), 400

        # Verifica se o email já existe
        if Professor.query.filter_by(email=email).first():
            return jsonify({"msg": "error", "details": "Este e-mail já está cadastrado."}), 409 # Conflict

        new_prof = Professor(nome=nome, email=email, senha=senha)
        db.session.add(new_prof)
        db.session.commit()

        app.logger.info(f"Novo professor cadastrado: {new_prof.nome} ({new_prof.email})")
        return jsonify({
            "msg": "success",
            "details": "Professor cadastrado com sucesso!",
            "professor": new_prof.to_dict()
        }), 201 # Created
    except Exception as e:
        app.logger.error(f"Erro ao cadastrar professor: {e}", exc_info=True)
        return jsonify({
            "msg": "error",
            "details": "Ocorreu um erro ao cadastrar o professor. Tente novamente mais tarde."
        }), 500

@app.route("/api/login", methods=["POST"])
def login_professor():
    """Endpoint para autenticação de professor."""
    try:
       

        email = request.form.get("email")
        senha = request.form.get("senha")

        if not all([email, senha]):
            return jsonify({"msg": "error", "details": "Email e senha são obrigatórios."}), 400

        professor = Professor.query.filter_by(email=email).first()

        if professor and professor.check_password(senha):
            session['prof_id'] = professor.id
            session['prof_nome'] = professor.nome
            session.permanent = True # Garante que a sessão seja permanente
            app.logger.info(f"Login bem-sucedido para: {professor.nome}")
            return jsonify({
                "msg": "success",
                "details": "Login realizado com sucesso!",
                "professor": professor.to_dict()
            }, 200)
        else:
            app.logger.warning(f"Tentativa de login falha para o email: {email}")
            return jsonify({"msg": "error", "details": "Credenciais inválidas."}), 401 # Unauthorized
    except Exception as e:
        app.logger.error(f"Erro no login do professor: {e}", exc_info=True)
        return jsonify({"msg": "error", "details": "Erro interno do servidor."}), 500

@app.route("/api/logout", methods=["POST"])
@auth_required
def logout_professor():
    """Endpoint para fazer logout do professor."""
    prof_nome = session.get('prof_nome', 'Desconhecido')
    session.pop('prof_id', None)
    session.pop('prof_nome', None)
    app.logger.info(f"Logout realizado para: {prof_nome}")
    return jsonify({"msg": "success", "details": "Logout realizado com sucesso."}), 200

@app.route("/api/agenda-sala", methods=["POST"])
@auth_required
def agenda_sala():
    """Endpoint para agendar uma sala."""
    try:
        professor_id = session.get("prof_id")

        if not professor_id:
            return jsonify({"msg": "error", "details": "Professor não autenticado."}), 401 # Unauthorized

        tipo_agendamento = "sala-maker"
        dia_str = request.form.get("dia") # Ex: "2024-06-15"
        print(f"Dia recebido: {dia_str}")
        hora_opcao = request.form.get("opcao-agendamento") # Ex: "08:00-10:00"
        print(f"Opção de horário recebida: {hora_opcao}")

        if not hora_opcao:
            return jsonify({"msg": "error", "details": "Opção de horário é obrigatória."}), 400

        hora = hora_opcao.strip().split("-")
        if len(hora) != 2:
            return jsonify({"msg": "error", "details": "Formato de opção de agendamento inválido. Use HH:MM-HH:MM."}), 400

        hora_inicio_str = hora[0].strip() # Ex: "08:00"
        print(f"Hora de início (string): {hora_inicio_str}")
        hora_termino_str = hora[1].strip() # Ex: "10:00"
        print(f"Hora de término (string): {hora_termino_str}")

        if not all([tipo_agendamento, dia_str, hora_inicio_str, hora_termino_str]):
            return jsonify({"msg": "error", "details": "Todos os campos (tipo, dia, hora_inicio, hora_termino) são obrigatórios."}), 400

        try:
            # Parsear data e horas
            dia = datetime.datetime.strptime(dia_str, "%Y-%m-%d").date()
            
            # Combine a data com as strings de hora para criar objetos datetime completos
            # Adicionando informações de fuso horário, se BRASILIA_TZ estiver disponível
            if BRASILIA_TZ:
                # Cria datetime naive (sem timezone)
                hora_inicio_naive = datetime.datetime.combine(dia, datetime.datetime.strptime(hora_inicio_str, "%H:%M").time())
                hora_termino_naive = datetime.datetime.combine(dia, datetime.datetime.strptime(hora_termino_str, "%H:%M").time())
                # Aplica o timezone de Brasília
                hora_inicio_completa = BRASILIA_TZ.localize(hora_inicio_naive)
                hora_termino_completa = BRASILIA_TZ.localize(hora_termino_naive)

                # Converte para UTC antes de salvar
                hora_inicio_utc = hora_inicio_completa.astimezone(pytz.utc)
                hora_termino_utc = hora_termino_completa.astimezone(pytz.utc)
            else:
                # Se não houver fuso horário, use datetime simples (não recomendado para produção)
                hora_inicio_completa = datetime.datetime.combine(dia, datetime.datetime.strptime(hora_inicio_str, "%H:%M").time())
                hora_termino_completa = datetime.datetime.combine(dia, datetime.datetime.strptime(hora_termino_str, "%H:%M").time())

        except ValueError:
            return jsonify({"msg": "error", "details": "Formato de data ou hora inválido. Use YYYY-MM-DD para dia e HH:MM para horas."}), 400

        # Validação de lógica de agendamento
        if hora_inicio_utc >= hora_termino_utc:
            return jsonify({"msg": "error", "details": "A hora de início deve ser anterior à hora de término."}), 400
        
        # Não permitir agendamentos no passado
        if hora_termino_utc < datetime.datetime.now(pytz.utc):
            return jsonify({"msg": "error", "details": "Não é possível agendar para o passado."}), 400

        # Verificar conflitos de agendamento
        conflitos = Agendamento.query.filter(
            Agendamento.dia == dia,
            (Agendamento.hora_inicio < hora_termino_utc) &
            (Agendamento.hora_termino > hora_inicio_utc)
        ).all()
        print(Agendamento.query.all())

        if conflitos:
            conflitos_detalhes = [c.to_dict() for c in conflitos]
            app.logger.warning(f"Conflito de agendamento para professor {professor_id} no dia {dia_str}: {conflitos_detalhes}")
            return jsonify({
                "msg": "error",
                "details": "Já existe um agendamento conflitante neste dia e horário.",
                "conflitos": conflitos_detalhes
            }), 409 # Conflict

        new_agendamento = Agendamento(
            tipo=tipo_agendamento,
            hora_inicio=hora_inicio_utc,
            hora_termino=hora_termino_utc,
            professor_id=professor_id,
            dia=dia
        )

        db.session.add(new_agendamento)
        db.session.commit()

        app.logger.info(f"Agendamento criado: {new_agendamento}")
        return jsonify({
            "msg": "success",
            "details": "Agendamento concluído com sucesso!",
            "agendamento": new_agendamento.to_dict()
        }), 201 # Created
    except Exception as e:
        db.session.rollback() # Em caso de erro, desfaz a transação
        app.logger.error(f"Erro ao agendar sala: {e}", exc_info=True)
        return jsonify({
            "msg": "error",
            "details": "Ocorreu um erro inesperado ao agendar a sala. Tente novamente mais tarde."
        }), 500
    
@app.route("/api/cancelar-agendamento/<id_agendamento>", methods=["DELETE"])
@auth_required
def cancelar_agendamento(id_agendamento):
    """Endpoint para cancelar um agendamento."""
    try:
        professor_id = session.get("prof_id")

        agendamento = Agendamento.query.filter_by(id=id_agendamento, professor_id=professor_id).first()

        if not agendamento:
            app.logger.warning(f"Tentativa de cancelar agendamento não encontrado ou não autorizado: ID={id_agendamento}, ProfessorID={professor_id}")
            return jsonify({"msg": "error", "details": "Agendamento não encontrado ou você não tem permissão para cancelá-lo."}), 404 # Not Found

        db.session.delete(agendamento)
        db.session.commit()


        return jsonify({
            "msg": "success",
            "details": "Agendamento cancelado com sucesso!"
        }), 200 # OK
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao cancelar agendamento: {e}", exc_info=True)
        return jsonify({
            "msg": "error",
            "details": "Ocorreu um erro ao cancelar o agendamento. Tente novamente mais tarde."
        }), 500

@app.route("/api/agendamentos-professor", methods=["GET"])
@auth_required
def listar_agendamentos_professor():
    """Endpoint para listar os agendamentos de um professor logado."""
    try:
        professor_id = session.get("prof_id")

        # Filtra agendamentos a partir de hoje
        hoje = get_current_datetime_br().date()
        agendamentos = Agendamento.query.filter(
            Agendamento.professor_id == professor_id,
            Agendamento.dia >= hoje # Apenas agendamentos a partir de hoje
        ).order_by(Agendamento.dia, Agendamento.hora_inicio).all()

        agendamentos_json = [agendamento.to_dict() for agendamento in agendamentos]
        
        app.logger.info(f"Listando {len(agendamentos_json)} agendamentos para o professor {professor_id}")
        return jsonify({
            "msg": "success",
            "agendamentos": agendamentos_json
        }), 200
    except Exception as e:
        app.logger.error(f"Erro ao listar agendamentos do professor: {e}", exc_info=True)
        return jsonify({
            "msg": "error",
            "details": "Erro ao listar agendamentos. Tente novamente mais tarde."
        }), 500

@app.route("/api/check-login", methods=["GET"])
def check_login():
    """Endpoint para a verificação de login pelo JS."""
    if 'prof_id' in session:
        return jsonify({"logged_in": True, "prof_id": session.get('prof_id'), "prof_nome": session.get('prof_nome')}), 200
    return jsonify({"logged_in": False}), 200

# --- Inicialização do Banco de Dados e Aplicação ---
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

