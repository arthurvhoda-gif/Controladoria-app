from database import SessionLocal
from models import Usuario

email_teste = input("Digite o e-mail do usuário recém-criado: ").strip().lower()
senha_digitada = input("Digite a senha informada no cadastro: ").strip()

db = SessionLocal()
usuario = db.query(Usuario).filter(Usuario.email == email_teste).first()

if not usuario:
    print("\n[FALHA] Usuário não encontrado no banco de dados com este e-mail.")
else:
    print(f"\n[INFO] Usuário localizado: {usuario.nome} (Perfil: {getattr(usuario, 'perfil', 'N/A')})")
    print(f"[INFO] Senha armazenada no banco: {usuario.senha}")
    
    # Checagem direta (texto puro)
    if usuario.senha == senha_digitada:
        print("[SUCESSO] A senha confere em texto puro!")
    else:
        # Checagem via bcrypt/hash
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            valida = pwd_context.verify(senha_digitada, usuario.senha)
            if valida:
                print("[SUCESSO] A senha confere via hash bcrypt!")
            else:
                print("[FALHA] O hash armazenado não bate com a senha digitada.")
        except Exception as e:
            print(f"[AVISO] Não foi possível verificar hash bcrypt: {e}")

db.close()