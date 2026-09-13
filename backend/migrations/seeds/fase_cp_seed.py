from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contents.models.cp import Cp
from app.domains.contents.models.fase import Fase

async def seed_fase_and_cp(session: AsyncSession):
    fase_e = Fase(kode="E")
    fase_f = Fase(kode="F")
    session.add_all([fase_e, fase_f])
    await session.flush()

    cp1 = Cp(
        fase_id=fase_e.id, 
        domain="Aljabar dan Fungsi", 
        cp_text="Fungsi Invers"
    )
    cp2 = Cp(
        fase_id=fase_e.id, 
        domain="Geometri", 
        cp_text="Lingkaran"
    )
    session.add_all([cp1, cp2])
    await session.flush()