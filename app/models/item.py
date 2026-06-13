from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class ProductItem(Base):
    __tablename__ = "product_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre = Column(String, nullable=False)
    precio = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)
    precio_peq = Column(String, nullable=True)
    precio_med = Column(String, nullable=True)
    precio_gran = Column(String, nullable=True)
    orden = Column(Integer, nullable=False, default=0)

    categoria = relationship("Category", back_populates="items")
