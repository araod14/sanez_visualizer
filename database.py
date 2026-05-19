from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship

DATABASE_URL = "sqlite:///./sanez.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    tiempo_rotacion_segundos = Column(Integer, default=10)


class Background(Base):
    __tablename__ = "backgrounds"
    id = Column(Integer, primary_key=True)   # 1 a 4
    ruta_archivo = Column(String, nullable=True)
    orden = Column(Integer)


class Category(Base):
    __tablename__ = "categories"
    clave = Column(String, primary_key=True)   # ron, whisky, cerveza, sangria
    nombre = Column(String, nullable=False)
    orden = Column(Integer, default=0)
    items = relationship(
        "ProductItem",
        back_populates="categoria",
        order_by="ProductItem.orden",
        cascade="all, delete-orphan",
    )


class ProductItem(Base):
    __tablename__ = "product_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    categoria_clave = Column(String, ForeignKey("categories.clave"), nullable=False)
    nombre = Column(String, nullable=False)
    precio = Column(Float, nullable=False)
    orden = Column(Integer, default=0)
    categoria = relationship("Category", back_populates="items")


CATEGORIAS_DEFAULT = [
    {"clave": "ron",     "nombre": "Ron",     "orden": 1},
    {"clave": "whisky",  "nombre": "Whisky",  "orden": 2},
    {"clave": "cerveza", "nombre": "Cerveza", "orden": 3},
    {"clave": "sangria", "nombre": "Sangría", "orden": 4},
]


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(Settings).first():
            db.add(Settings(id=1, tiempo_rotacion_segundos=10))

        for i in range(1, 5):
            if not db.query(Background).filter(Background.id == i).first():
                db.add(Background(id=i, ruta_archivo=None, orden=i))

        for c in CATEGORIAS_DEFAULT:
            if not db.query(Category).filter(Category.clave == c["clave"]).first():
                db.add(Category(**c))

        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
