from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contents.models.cp import Cp
from app.domains.contents.models.fase import Fase

async def seed_fase_and_cp(session: AsyncSession):
    fase_e = Fase(kode="E")
    fase_f = Fase(kode="F")
    session.add_all([fase_e, fase_f])
    await session.flush()

    # Fase E
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
    cp3 = Cp(
            fase_id=fase_e.id, 
            domain="Bilangan", 
            cp_text="Bilangan dan Sifat-Sifatnya"
        )
    cp4 = Cp(
        fase_id=fase_e.id, 
        domain="Analisis Data dan Peluang", 
        cp_text="Analisis Data dan Peluang"
    )

    # Fase F
    cp5 = Cp(
        fase_id=fase_f.id, 
        domain="Aljabar dan Fungsi", 
        cp_text="Fungsi Invers"
    )
    cp6 = Cp(
        fase_id=fase_f.id, 
        domain="Geometri", 
        cp_text="Lingkaran"
    )
    cp7 = Cp(
            fase_id=fase_f.id, 
            domain="Bilangan", 
            cp_text="Bilangan dan Sifat-Sifatnya"
        )
    cp8 = Cp(
        fase_id=fase_f.id, 
        domain="Analisis Data dan Peluang", 
        cp_text="Analisis Data dan Peluang"
    )
    cp9 = Cp(
        fase_id=fase_f.id, 
        domain="Fungsi", 
        cp_text="Fungsi"
    )
    cp10 = Cp(
        fase_id=fase_f.id, 
        domain="Kalkulus", 
        cp_text="Kalkulus"
    )
    session.add_all([cp1, cp2, cp3, cp4, cp5, cp6, cp7, cp8, cp9, cp10])
    await session.flush()