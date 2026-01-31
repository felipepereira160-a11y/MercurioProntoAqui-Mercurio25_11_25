import streamlit_authenticator as stauth

# A senha que queremos hashear para o admin
password_to_hash = "admin123"

# O método espera uma lista de senhas
hashed_password_list = stauth.Hasher([password_to_hash]).generate()

# O resultado também é uma lista, então pegamos o primeiro item
final_hash = hashed_password_list[0]

print("--- HASH PARA O ADMIN ---")
print(final_hash)
print("--- COPIE A LINHA ACIMA E COLE AQUI ---")