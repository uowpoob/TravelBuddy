from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for business models; checkpoint tables are managed separately."""
