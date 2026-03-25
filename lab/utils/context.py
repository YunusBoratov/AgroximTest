def get_xulosa_context(xulosa):
    namuna = xulosa.namuna

    return {
        "ariza_raqami": namuna.ariza_raqami,
        "korxona": namuna.korxona_nomi,
        "masul_shaxs": namuna.masul_shaxs,
        "namuna_turi": namuna.namuna_turi,
        "sana": xulosa.sana,
        "matn": xulosa.matn,
        "umumiy_summa": getattr(namuna, "umumiy_summa", 0),
        "status": xulosa.get_status_display(),
        "verify_token": xulosa.verify_token,
        "bandlar": [],  # keyin professional PDF bosqichida ulaymiz
    }