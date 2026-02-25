from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:password@localhost/patientdb"
)
