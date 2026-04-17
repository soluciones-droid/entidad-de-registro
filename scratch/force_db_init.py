
from app.db import engine, Base
from app.db_models import CaptureSessionORM, RegistrationRequestORM

def force_init():
    print("Iniciando creación de tablas...")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas exitosamente.")

if __name__ == "__main__":
    force_init()
