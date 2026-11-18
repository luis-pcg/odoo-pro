MODULE = "hms_partner"

company = env.ref("base.main_company")
do = env.ref("base.do")

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
env["ir.module.module"].search(
    [("name", "in", [MODULE, "contacts", "base"]), ("state", "=", "installed")]
)._update_translations(filter_lang="es_DO", overwrite=True)

company.write({"name": "Centro Médico INDEXA", "country_id": do.id})

Speciality = env["hms.medical.speciality"]


def speciality(name, anest=False):
    return Speciality.search([("name", "=", name)], limit=1) or Speciality.create(
        {"name": name, "is_anesthesiologist": anest}
    )


cardio = speciality("Cardiología")
anest = speciality("Anestesiología", True)
pediatria = speciality("Pediatría")
gineco = speciality("Ginecología y Obstetricia")

Partner = env["res.partner"]


def partner(name, vals):
    rec = Partner.search([("name", "=", name)], limit=1)
    vals = dict(vals, name=name, country_id=do.id)
    if rec:
        rec.write(vals)
        return rec
    return Partner.create(vals)


ars_humano = partner("ARS Humano", {
    "medical_contact_type": "insurance", "insurance_type": "private",
    "vat": "101001577", "phone": "809-476-3535", "city": "Santo Domingo",
})
partner("ARS Universal", {
    "medical_contact_type": "insurance", "insurance_type": "private",
    "vat": "101084456", "phone": "809-544-7111", "city": "Santo Domingo",
})
partner("SeNaSa", {
    "medical_contact_type": "insurance", "insurance_type": "public",
    "vat": "401516454", "phone": "809-732-7272", "city": "Santo Domingo",
})
doctor = partner("Dra. Carmen Rosario", {
    "medical_contact_type": "contact",
    "medical_speciality_ids": [(6, 0, [anest.id, cardio.id])],
    "phone": "809-555-0101", "email": "crosario@example.com",
})
patient = partner("Juan Pérez Almonte", {
    "medical_contact_type": "patient",
    "medical_record": "EXP-2026-00125",
    "insurance_partner_id": ars_humano.id,
    "affiliate_id": "AFI-778899",
    "phone": "829-555-0177",
})
partner("María Gómez Santana", {
    "medical_contact_type": "patient",
    "medical_record": "EXP-2026-00126",
    "phone": "849-555-0132",
})


def demo_action(xmlid, vals):
    old = env.ref(f"{MODULE}.{xmlid}", raise_if_not_found=False)
    if old:
        old.unlink()
    env["ir.model.data"].search([("module", "=", MODULE), ("name", "=", xmlid)]).unlink()
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": MODULE, "name": xmlid, "model": "ir.actions.act_window",
        "res_id": act.id, "noupdate": True,
    })
    return act


demo_action("demo_aseguradora", {
    "name": "Aseguradora", "res_model": "res.partner", "view_mode": "form", "res_id": ars_humano.id,
})
demo_action("demo_medico", {
    "name": "Médico", "res_model": "res.partner", "view_mode": "form", "res_id": doctor.id,
})
demo_action("demo_paciente", {
    "name": "Paciente", "res_model": "res.partner", "view_mode": "form", "res_id": patient.id,
})
demo_action("demo_contactos", {
    "name": "Contactos", "res_model": "res.partner", "view_mode": "list,form",
})

env.cr.commit()
print(
    "SEED OK | doctor anest:", doctor.is_anesthesiologist, doctor.has_medical_speciality,
    "| ars is_insurance:", ars_humano.is_insurance,
    "| name_search EXP:", Partner.name_search("EXP-2026-00125"),
)
