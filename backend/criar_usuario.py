import bcrypt
from database import SessionLocal
import models

def get_password_hash(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode("utf-8")

print("\n=== CRIAR USUÁRIO NO BANCO DE DADOS ===\n")

nome = input("Nome completo: ").strip()
email = input("E-mail de acesso: ").strip().lower()
senha = input("Senha: ").strip()

print("\nSelecione o perfil de acesso:")
print("1 - Solicitante (Cria e acompanha pedidos de compra)")
print("2 - Controladoria (Acesso total: aprova compras e gerencia checklists)")
print("3 - Checklist (Acesso restrito SOMENTE à aba de Checklist/Vistorias)")
opcao = input("Opção (1, 2 ou 3): ").strip()

if opcao == "2":
    perfil = "Controladoria"
elif opcao == "3":
    perfil = "Checklist"
else:
    perfil = "Solicitante"

if not nome or not email or not senha:
    print("\n[ERRO] Todos os campos são obrigatórios.")
    exit()

db = SessionLocal()

try:
    existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    senha_hash = get_password_hash(senha)

    if existente:
        print(f"\n[AVISO] O e-mail '{email}' já existia. Atualizando senha e perfil...")
        existente.nome = nome
        existente.senha = senha_hash
        existente.perfil = perfil
        db.commit()
        print("[SUCESSO] Usuário atualizado com sucesso!")
    else:
        novo_usuario = models.Usuario(
            nome=nome, email=email, senha=senha_hash, perfil=perfil
        )
        db.add(novo_usuario)
        db.commit()
        print("[SUCESSO] Usuário criado com sucesso!")

    print(f"Nome: {nome} | E-mail: {email} | Perfil: {perfil}\n")
except Exception as e:
    db.rollback()
    print(f"\n[ERRO ao salvar no banco]: {e}\n")
finally:
    db.close()