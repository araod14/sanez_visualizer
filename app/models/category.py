from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "orden", name="uq_category_user_orden"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre = Column(String, nullable=False)
    orden = Column(Integer, nullable=False, default=0)
    background_path = Column(String, nullable=True)
    precio_modo = Column(String, nullable=False, default="usd_fijo", server_default="usd_fijo")

    usuario = relationship("User", back_populates="categorias")
    items = relationship(
        "ProductItem",
        back_populates="categoria",
        order_by="ProductItem.orden",
        cascade="all, delete-orphan",
    )
