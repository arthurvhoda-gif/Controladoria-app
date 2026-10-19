from database import SessionLocal
from models import Usuario

try:
  db = SessionLocal()
  usuarios = db.query(Usuario).all()
  print("\n================ USUÁRIOS CADASTRADOS ================")
  if not usuarios:
    print("Nenhum usuário encontrado na tabela.")
  for u in usuarios:
    print(
        f"ID: {u.id} | Nome: {u.nome} | E-mail: {u.email} | Perfil:"
        f" {getattr(u, 'perfil', 'N/A')}"
    )
  print("======================================================\n")
  db.close()
except Exception as e:
  print(f"\nErro ao consultar o banco de dados: {e}\n")