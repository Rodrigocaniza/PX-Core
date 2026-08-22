# Auditor — PASS

- BC Seguridad decide identidad, branch, licencia, capacidad `bc.sync`, revocación y vigencia.
- Firma/validación delegadas a `issue_credential`/`verify_credential`; anti-replay a `NonceLedger`.
- Sync vuelve a autorizar antes de publicar y antes de cada retry.
- Installation/branch autodeclarados, alteración, replay y timestamp inválido fallan cerrados.
- Renovación/rotación no modifica ni pierde el evento durable del outbox.
- Auditoría guarda acciones y motivos sanitizados, nunca claves o secretos sellados.
- El resolver remoto real queda como puerto porque Seguridad aún no fue promovida al árbol de Sync.
