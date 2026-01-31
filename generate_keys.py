import streamlit_authenticator as stauth
import sys

# Pega as senhas dos argumentos da linha de comando
passwords_to_hash = sys.argv[1:]

if not passwords_to_hash:
    print("Por favor, forneça as senhas como argumentos.")
    print("Exemplo: python generate_keys.py suapassword123 outra_senha")
    sys.exit(1)

hashed_passwords = stauth.Hasher(passwords_to_hash).generate()
print("Copie os hashes gerados para o seu arquivo config.yaml:")
for i, hashed_pw in enumerate(hashed_passwords):
    print(f"Senha {i+1}: {hashed_pw}")

