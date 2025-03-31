from werkzeug.security import check_password_hash

hash_almacenado = "scrypt:32768:8:1$zR4BAzjjzsKU979a$17e43b35e98c6a1b9197d2929f44996f54691e29b46ae3fa8c25fdbe86b1a4e22e"
password_ingresada = "admin1"  # Cambia esto por la contraseña real

if check_password_hash(hash_almacenado, password_ingresada):
    print("¡Contraseña correcta!")
else:
    print("Contraseña incorrecta.")
