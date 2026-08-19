from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import comision_policy
from .models import Alert, CashSnapshot, Unit


class CentralRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
        finally:
            con.close()

    def migrate(self):
        with self.connection() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS central_users(
              username TEXT PRIMARY KEY COLLATE NOCASE, password_hash TEXT NOT NULL,
              salt TEXT NOT NULL, role TEXT NOT NULL, unit TEXT, active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cash_snapshots(
              event_id TEXT PRIMARY KEY, unit TEXT NOT NULL, business_date TEXT NOT NULL,
              status TEXT NOT NULL, opening_cash INTEGER NOT NULL, income INTEGER NOT NULL,
              cash INTEGER NOT NULL, card_check INTEGER NOT NULL, expenses INTEGER NOT NULL,
              withdrawals INTEGER NOT NULL, expected_cash INTEGER NOT NULL,
              counted_cash INTEGER, entry_count INTEGER NOT NULL,
              source_updated_at TEXT NOT NULL, received_at TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_unit_time ON cash_snapshots(unit, source_updated_at DESC);
            CREATE TABLE IF NOT EXISTS central_alerts(
              id TEXT PRIMARY KEY, unit TEXT NOT NULL, kind TEXT NOT NULL,
              severity TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL,
              created_at TEXT NOT NULL, acknowledged_at TEXT, acknowledged_by TEXT,
              UNIQUE(unit, kind, status)
            );
            CREATE TABLE IF NOT EXISTS central_audit(
              id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
              target TEXT NOT NULL, result TEXT NOT NULL, details_json TEXT NOT NULL,
              recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operational_alert_state(
              alert_id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_by TEXT NOT NULL,
              updated_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
              FOREIGN KEY(alert_id) REFERENCES central_alerts(id)
            );
            CREATE TABLE IF NOT EXISTS central_messages(
              id TEXT PRIMARY KEY, target_unit TEXT NOT NULL, target_pc TEXT,
              body TEXT NOT NULL, status TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
              created_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS central_outbox(
              id TEXT PRIMARY KEY, aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
              event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daily_field_reviews(
              unit TEXT NOT NULL, business_date TEXT NOT NULL, field_name TEXT NOT NULL,
              reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL,
              PRIMARY KEY(unit,business_date,field_name)
            );
            CREATE TABLE IF NOT EXISTS message_delivery(
              message_id TEXT PRIMARY KEY, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              last_attempt_at TEXT, next_attempt_at TEXT, delivered_at TEXT, confirmed_at TEXT,
              cancelled_at TEXT, cancelled_by TEXT, cancel_reason TEXT,
              error_code TEXT, error_message TEXT, updated_at TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES central_messages(id)
            );
            CREATE TABLE IF NOT EXISTS message_delivery_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT NOT NULL,
              from_state TEXT, to_state TEXT NOT NULL, actor TEXT NOT NULL,
              details_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES central_messages(id)
            );
            CREATE TABLE IF NOT EXISTS message_receipts(
              receipt_id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE, receiver TEXT NOT NULL,
              received_at TEXT NOT NULL, payload_json TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES central_messages(id)
            );
            CREATE TABLE IF NOT EXISTS simulated_receiver_inbox(
              idempotency_key TEXT PRIMARY KEY, receipt_id TEXT NOT NULL UNIQUE,
              message_id TEXT NOT NULL, receiver TEXT NOT NULL, received_at TEXT NOT NULL,
              envelope_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_delivery_state_next ON message_delivery(state,next_attempt_at);
            CREATE TABLE IF NOT EXISTS factufacil_sales(
              id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE, branch TEXT NOT NULL,
              source_sale_id TEXT NOT NULL, envelope TEXT NOT NULL, status TEXT NOT NULL,
              content_hash TEXT NOT NULL, payload_json TEXT NOT NULL, version INTEGER NOT NULL,
              loaded_by TEXT, loaded_at TEXT, receipt_number TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(branch,envelope)
            );
            CREATE TABLE IF NOT EXISTS factufacil_versions(
              sale_id TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
              PRIMARY KEY(sale_id,version), FOREIGN KEY(sale_id) REFERENCES factufacil_sales(id)
            );
            CREATE TABLE IF NOT EXISTS factufacil_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id TEXT NOT NULL,
              from_state TEXT, to_state TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, details_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
              FOREIGN KEY(sale_id) REFERENCES factufacil_sales(id)
            );
            CREATE INDEX IF NOT EXISTS idx_factufacil_status_date ON factufacil_sales(status,updated_at);
            CREATE TABLE IF NOT EXISTS commission_sales(
              id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE, branch TEXT NOT NULL,
              source_sale_id TEXT NOT NULL, saleswoman TEXT NOT NULL, sale_kind TEXT NOT NULL,
              sale_date TEXT NOT NULL, total_amount INTEGER NOT NULL, paid_amount INTEGER NOT NULL,
              balance_amount INTEGER NOT NULL, cancelled_date TEXT,
              voided INTEGER NOT NULL DEFAULT 0, void_reason TEXT, envelope TEXT NOT NULL DEFAULT '',
              content_hash TEXT NOT NULL, payload_json TEXT NOT NULL, version INTEGER NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(branch,source_sale_id)
            );
            CREATE TABLE IF NOT EXISTS commission_payments(
              id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES commission_sales(id),
              amount INTEGER NOT NULL, payment_date TEXT NOT NULL, kind TEXT NOT NULL,
              reference TEXT NOT NULL DEFAULT '', reverses_id TEXT,
              idempotency_key TEXT NOT NULL UNIQUE, client_key TEXT,
              actor TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS commission_entries(
              id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES commission_sales(id),
              sequence INTEGER NOT NULL, period TEXT, branch TEXT NOT NULL, saleswoman TEXT NOT NULL,
              sale_kind TEXT NOT NULL, status TEXT NOT NULL,
              gross_amount INTEGER NOT NULL, agreement_discount INTEGER NOT NULL DEFAULT 0,
              commissionable_base INTEGER NOT NULL DEFAULT 0,
              rate_bp INTEGER, commission_amount INTEGER, policy_status TEXT NOT NULL,
              policy_code TEXT, policy_version INTEGER, policy_effective_from TEXT, policy_scope TEXT,
              eligible_date TEXT, reviewed_by TEXT, reviewed_at TEXT, approved_by TEXT, approved_at TEXT,
              paid_at TEXT, payment_reference TEXT, observation TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(sale_id,sequence)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_entry_active
              ON commission_entries(sale_id) WHERE status<>'REVERTIDA';
            CREATE UNIQUE INDEX IF NOT EXISTS idx_commission_entry_period
              ON commission_entries(sale_id,period) WHERE period IS NOT NULL AND status<>'REVERTIDA';
            CREATE INDEX IF NOT EXISTS idx_commission_entries_period
              ON commission_entries(period,branch,saleswoman);
            CREATE TABLE IF NOT EXISTS commission_entry_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id TEXT NOT NULL,
              sale_id TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, details_json TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_commission_history_entry ON commission_entry_history(entry_id,id);
            CREATE TABLE IF NOT EXISTS commission_policies(
              id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_value TEXT NOT NULL DEFAULT '',
              rate_bp INTEGER NOT NULL, approval_status TEXT NOT NULL,
              code TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 1,
              effective_from TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(scope,scope_value)
            );
            CREATE TABLE IF NOT EXISTS commission_policy_versions(
              id INTEGER PRIMARY KEY AUTOINCREMENT, policy_id TEXT NOT NULL, code TEXT NOT NULL,
              scope TEXT NOT NULL, scope_value TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL,
              rate_bp INTEGER NOT NULL, approval_status TEXT NOT NULL, effective_from TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL, recorded_at TEXT NOT NULL,
              UNIQUE(policy_id,version)
            );
            -- Tabla de la generación 5, congelada en la 7: guardaba **el estado** de la fijación,
            -- una fila por período. Ya no se lee ni se escribe. No se borra —nada de lo que el
            -- sistema afirmó alguna vez se borra— pero la verdad vive ahora en el libro de eventos
            -- de abajo, que sí puede expresar que una fijación se retiró.
            CREATE TABLE IF NOT EXISTS commission_rated_periods(
              period TEXT PRIMARY KEY,
              rate_bp INTEGER NOT NULL, policy_code TEXT NOT NULL, policy_version INTEGER NOT NULL,
              policy_effective_from TEXT NOT NULL, policy_scope TEXT NOT NULL,
              first_rated_by TEXT NOT NULL, first_rated_at TEXT NOT NULL,
              origin TEXT NOT NULL DEFAULT 'RATED'
            );
            -- Libro append-only de la tasa de cada período: `PINNED` cuando un hecho económico
            -- oficial la fija, `UNPINNED` cuando desaparece el último hecho vivo que la justificaba.
            --
            -- Es un libro y no un estado porque la tasa de un período **no es inmutable por haber
            -- existido alguna vez un hecho que la justificó**: si esa aprobación se revierte o esa
            -- venta se anula, la justificación desaparece y el período vuelve a ser resoluble. Lo
            -- que no desaparece nunca es el rastro: cada fijación y cada retirada quedan aquí, con
            -- su causa, su actor y su fecha, y la secuencia completa
            -- `PINNED → UNPINNED → PINNED` se lee entera.
            --
            -- El estado vigente de un período es su **último** evento. Nada se actualiza y nada se
            -- borra: volver a fijar es un evento más, no una reescritura del anterior.
            CREATE TABLE IF NOT EXISTS commission_period_rate_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              period TEXT NOT NULL,
              event TEXT NOT NULL,
              rate_bp INTEGER NOT NULL,
              policy_code TEXT NOT NULL, policy_version INTEGER NOT NULL,
              policy_effective_from TEXT NOT NULL, policy_scope TEXT NOT NULL,
              origin TEXT NOT NULL,
              entry_id TEXT, sale_id TEXT,
              reason TEXT NOT NULL DEFAULT '',
              actor TEXT NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_commission_period_rate_events
              ON commission_period_rate_events(period,id);
            """)
            self._add_missing_columns(con)
            self._migrate_commission_policy(con)
            self._backfill_period_rate_events(con)
            con.commit()

    @staticmethod
    def _add_missing_columns(con):
        """Migración aditiva idempotente para bases de pilotos ya creadas."""
        additions = (
            ("commission_payments", "client_key", "TEXT"),
            ("commission_policies", "code", "TEXT NOT NULL DEFAULT ''"),
            ("commission_policies", "version", "INTEGER NOT NULL DEFAULT 1"),
            ("commission_policies", "effective_from", "TEXT NOT NULL DEFAULT ''"),
            ("commission_entries", "policy_code", "TEXT"),
            ("commission_entries", "policy_version", "INTEGER"),
            ("commission_entries", "policy_effective_from", "TEXT"),
            ("commission_entries", "policy_scope", "TEXT"),
        )
        for table, column, kind in additions:
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_commission_payments_client_key"
                    " ON commission_payments(client_key)")

    def _migrate_commission_policy(self, con):
        """Instala la política canónica del 1% sobre bases que traen el piloto sintético.

        Es idempotente y no toca dinero: las liquidaciones ya pagadas conservan su
        `rate_bp` y su `commission_amount` históricos; sólo se les reemplaza la etiqueta
        de política retirada por `POLITICA_HISTORICA_PREVIA`, que dice la verdad sobre
        ellas sin afirmar que se calcularon con la regla aprobada. Cada retiro queda
        asentado en la auditoría con el valor anterior, así nada desaparece en silencio.
        """
        now = datetime.now().astimezone().isoformat()
        seed = comision_policy.canonical_seed()

        retired = con.execute(
            "SELECT id,scope,scope_value,rate_bp,approval_status FROM commission_policies"
            " WHERE approval_status IN (?,?) OR scope<>?",
            (*comision_policy.RETIRED_POLICY_STATUSES, comision_policy.CANONICAL_SCOPE),
        ).fetchall()
        for row in retired:
            # Un porcentaje por vendedora o por local contradice la decisión aprobada:
            # el 1% es igual para todas. Se retira con su valor previo en la auditoría.
            self.audit(con, "MIGRACION", "COMMISSION_POLICY_RETIRED",
                       f"{row['scope']}:{row['scope_value']}", details={
                           "rate_bp": row["rate_bp"], "approval_status": row["approval_status"],
                           "replaced_by": seed["code"]})
            if row["scope"] != comision_policy.CANONICAL_SCOPE:
                con.execute("DELETE FROM commission_policies WHERE id=?", (row["id"],))

        current = con.execute(
            "SELECT * FROM commission_policies WHERE scope=? AND scope_value=''",
            (comision_policy.CANONICAL_SCOPE,),
        ).fetchone()
        if current is None or current["approval_status"] != comision_policy.POLICY_CANONICAL:
            con.execute(
                "INSERT INTO commission_policies(id,scope,scope_value,rate_bp,approval_status,code,version,"
                "effective_from,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(scope,scope_value) DO UPDATE SET rate_bp=excluded.rate_bp,"
                "approval_status=excluded.approval_status,code=excluded.code,version=excluded.version,"
                "effective_from=excluded.effective_from,created_by=excluded.created_by,created_at=excluded.created_at",
                (seed["id"], seed["scope"], seed["scope_value"], seed["rate_bp"], seed["approval_status"],
                 seed["code"], seed["version"], seed["effective_from"], "MIGRACION", now),
            )
            con.execute(
                "INSERT OR IGNORE INTO commission_policy_versions(policy_id,code,scope,scope_value,version,"
                "rate_bp,approval_status,effective_from,note,actor,recorded_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (seed["id"], seed["code"], seed["scope"], seed["scope_value"], seed["version"],
                 seed["rate_bp"], seed["approval_status"], seed["effective_from"],
                 "decisión aprobada: 1% general para toda vendedora y local", "MIGRACION", now),
            )

        for status in comision_policy.RETIRED_POLICY_STATUSES:
            # La liquidación conserva su importe; sólo deja de mostrar una etiqueta retirada.
            con.execute(
                "UPDATE commission_entries SET policy_status=? WHERE policy_status=? AND rate_bp IS NOT NULL",
                (comision_policy.POLICY_LEGACY, status),
            )
            con.execute(
                "UPDATE commission_entries SET policy_status=? WHERE policy_status=? AND rate_bp IS NULL",
                (comision_policy.POLICY_ABSENT, status),
            )

    def _backfill_period_rate_events(self, con):
        """Reconcilia el libro de tasas de **todos** los períodos al abrir la base.

        No es una siembra aparte: es la misma reconciliación que corre en caliente, aplicada a cada
        período que tenga hechos vivos o que ya tenga libro. Tener dos rutas con dos reglas fue lo
        que costó `AB1-g6`, `AB1-g7` y `AB1-g8`, una vez por generación, cada vez en una columna
        distinta. Aquí hay una sola función de decisión —`comision_policy.resolve_period_rate`— y
        una sola de escritura.

        **La migración no inventa hechos.** Que un período no tenga ningún hecho vivo es
        *observable*, no fabricado, y aplicar la regla a esa observación es exactamente lo que hace
        `_set_status` en cada transición. Por eso una fijación heredada que hoy nada sostiene se
        retira aquí, con `origin='MIGRACION'` para que se distinga de un retiro operativo. Lo que
        la migración sigue sin hacer es **elegir**: ante hechos vivos con tasas distintas no fija
        nada y lo asienta, porque desempatar sería decidir por el propietario.

        No escribe una sola vez sobre `commission_entries`.
        """
        periods = {row[0] for row in con.execute(
            f"SELECT DISTINCT {comision_policy.PERIOD_KEY_SQL} FROM commission_entries e"
            f" WHERE e.period IS NOT NULL")}
        # La clave del libro se normaliza igual que la de las liquidaciones: una fila legada con
        # fecha completa producía un período fantasma que sobrevivía a toda reapertura y que la
        # publicación siguiente declaraba «protegido» sin existir.
        periods |= {row[0] for row in con.execute(
            f"SELECT DISTINCT {comision_policy.PERIOD_KEY_SQL} FROM commission_period_rate_events e")}
        for period in sorted(periods):
            self.reconcile_period_rate(con, period, "MIGRACION", "MIGRACION",
                                       reason="reconciliacion al abrir la base migrada")

        # Una fijación heredada de la generación 5, en la tabla congelada, que hoy nada sostiene.
        # La fila vieja no se toca; sólo se deja dicho por qué no se arrastró.
        known = {row[0] for row in con.execute(
            "SELECT DISTINCT period FROM commission_period_rate_events")}
        known = {str(row)[:7] for row in known}
        legacy = {str(row[0])[:7] for row in con.execute(
            "SELECT period FROM commission_rated_periods")}
        for period in sorted(legacy - known):
            self._audit_seed_once(
                con, "COMMISSION_PERIOD_RATE_SEED_SKIPPED", period,
                {"reason": "SIN_HECHO_ECONOMICO_VIVO",
                 "note": "fijacion heredada de la generacion 5 sin hecho vivo que la justifique"})

    @staticmethod
    def last_period_rate_event(con, period):
        """Último evento del período: **la** respuesta a «¿qué dice el libro hoy?».

        Estaba escrita en tres sitios —dos con el mismo SQL copiado literalmente y uno con un
        `JOIN` sobre `MAX(id)`—. La decisión se unificó en `resolve_period_rate` y la escritura en
        `record_period_rate_event`, pero la lectura del estado actual se había quedado fuera, que
        es justo donde una corrección futura puede volver a tocar una mitad y no la otra.
        """
        return con.execute(
            "SELECT * FROM commission_period_rate_events WHERE period=? ORDER BY id DESC LIMIT 1",
            (str(period)[:7],)).fetchone()

    @staticmethod
    def pinned_periods_from(con, effective_from):
        """Períodos hoy fijados cuyo mes no es anterior a esa vigencia.

        Se resuelve con la misma lectura por período, no con un `JOIN` propio: son la misma
        pregunta hecha sobre muchos períodos.
        """
        periods = [row[0] for row in con.execute(
            f"SELECT DISTINCT {comision_policy.PERIOD_KEY_SQL} AS period_key"
            "   FROM commission_period_rate_events e"
            "  WHERE substr(e.period,1,7) >= substr(?,1,7) ORDER BY period_key", (effective_from,))]
        fijados = []
        for period in periods:
            last = CentralRepository.last_period_rate_event(con, period)
            if last is not None and last["event"] == "PINNED":
                fijados.append(period)
        return fijados

    def live_official_facts(self, con, period):
        """Hechos económicos oficiales vivos de un período. Una sola consulta para todo el sistema."""
        return con.execute(comision_policy.live_official_facts_sql(by_period=True),
                           (str(period)[:7],)).fetchall()

    def reconcile_period_rate(self, con, period, actor, origin, *, entry_id=None, sale_id=None,
                              reason=""):
        """Lleva el libro de un período al estado que sus hechos vivos justifican. Único decisor.

        Compara lo que el libro dice hoy con lo que la regla dice que debería decir, y escribe la
        diferencia:

        * sin fijar y con un hecho que lo justifique → `PINNED`;
        * fijado y sin ningún hecho vivo que lo sostenga → `UNPINNED`;
        * fijado a una tasa que **ningún** hecho vivo lleva → `UNPINNED` y, si los que quedan
          coinciden entre sí, `PINNED` a la tasa que de verdad los respalda;
        * hechos vivos con tasas distintas → no se fija nada y se asienta el conflicto;
        * ya coincide → no escribe nada, que es lo que la hace idempotente.

        Fijar y soltar dejan de ser dos operaciones con dos criterios: son la misma pregunta
        contestada en un sitio. Se invoca desde `_set_status` —por donde pasa toda transición— y
        desde la apertura de la base, de modo que ninguna ruta puede saltársela.
        """
        period = str(period or "")[:7]
        if not period:
            return False
        facts = self.live_official_facts(con, period)
        resolution = comision_policy.resolve_period_rate(facts)
        last = self.last_period_rate_event(con, period)
        current = int(last["rate_bp"]) if last is not None and last["event"] == "PINNED" else None

        if resolution is comision_policy.PERIOD_RATE_AMBIGUOUS:
            desired, chosen = None, None
            self._audit_conflict_once(
                con, period, actor,
                {"reason": "EVIDENCIA_DISCREPANTE",
                 "rates_bp": sorted({int(f["rate_bp"]) for f in facts}),
                 "entries": [f["id"] for f in facts]})
        elif resolution is None:
            desired, chosen = None, None
        else:
            chosen = resolution
            desired = int(chosen["rate_bp"])

        if desired == current:
            return False

        changed = False
        if current is not None:
            self.record_period_rate_event(
                con, period, "UNPINNED", rate_bp=current, policy_code=last["policy_code"],
                policy_version=last["policy_version"],
                policy_effective_from=last["policy_effective_from"],
                policy_scope=last["policy_scope"], origin=origin, actor=actor,
                entry_id=entry_id, sale_id=sale_id,
                reason=reason or "ningun hecho economico oficial vivo sostiene esta tasa")
            changed = True
        if desired is not None:
            boundary = ("PAGADA" if (chosen["paid_at"] is not None or chosen["status"] == "PAGADA")
                        else "APROBADA")
            self.record_period_rate_event(
                con, period, "PINNED", rate_bp=desired, policy_code=chosen["policy_code"],
                policy_version=chosen["policy_version"],
                policy_effective_from=chosen["policy_effective_from"],
                policy_scope=chosen["policy_scope"], origin=origin, actor=actor,
                entry_id=chosen["id"], sale_id=chosen["sale_id"],
                reason=f"hecho economico oficial vivo: {boundary}")
            changed = True
        return changed

    def record_period_rate_event(self, con, period, event, *, rate_bp, policy_code, policy_version,
                                 policy_effective_from, policy_scope, origin, actor, reason,
                                 entry_id=None, sale_id=None, recorded_at=None):
        """**Único escritor** del libro de tasas por período. Append-only: nunca actualiza ni borra.

        Vive en el repositorio, y no en el servicio, porque la migración también tiene que escribir
        el libro y no puede importar `comisiones` sin crear un ciclo. Que hubiera dos rutas de
        escritura —una en cada clase, con dos formatos de asiento— fue el bloqueante `L1-g7`: la
        propiedad «la secuencia `PINNED → UNPINNED → PINNED` está completa» no la garantizaba un
        escritor único sino dos que casualmente coincidían, y cualquier guarda añadida a uno no
        habría alcanzado al otro. Es exactamente la clase de divergencia que ya costó `AB1-g6`.

        Escribe el evento y su asiento en `central_audit` en la misma transacción, de modo que no
        existe un estado en el que uno esté sin el otro, y **siempre**: la siembra usaba antes un
        nombre de acción propio y desactivaba el asiento, de modo que quien contara fijaciones por
        la auditoría no veía las de la migración. Ahora `COMMISSION_PERIOD_RATE_PINNED` y
        `COMMISSION_PERIOD_RATE_UNPINNED` cubren las dos rutas, y el `origin` distingue cuál fue.
        """
        con.execute(
            "INSERT INTO commission_period_rate_events(period,event,rate_bp,policy_code,policy_version,"
            "policy_effective_from,policy_scope,origin,entry_id,sale_id,reason,actor,recorded_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (period, event, int(rate_bp), policy_code or comision_policy.CANONICAL_CODE,
             policy_version if policy_version is not None else comision_policy.CANONICAL_VERSION,
             policy_effective_from or comision_policy.CANONICAL_EFFECTIVE_FROM,
             policy_scope or comision_policy.CANONICAL_SCOPE, origin, entry_id, sale_id, reason,
             actor, recorded_at or datetime.now().astimezone().isoformat()),
        )
        action = ("COMMISSION_PERIOD_RATE_PINNED" if event == "PINNED"
                  else "COMMISSION_PERIOD_RATE_UNPINNED")
        self.audit(con, actor, action, period, details={
            "rate_bp": int(rate_bp), "origin": origin, "reason": reason, "entry_id": entry_id,
            "sale_id": sale_id, "policy_code": policy_code, "policy_version": policy_version,
            "policy_effective_from": policy_effective_from})

    def _audit_conflict_once(self, con, period, actor, details):
        """Asienta una discrepancia de tasas, una vez por **conflicto**, no una vez por período.

        `_audit_seed_once` deduplica por acción y objetivo, que es lo correcto para la apertura de
        la base —corre en cada arranque— pero silenciaba la segunda discrepancia distinta de un
        mismo mes cuando la reconciliación corre en caliente. Aquí la huella incluye las tasas en
        conflicto, así que un conflicto nuevo sí se asienta, y el actor es el que lo provocó y no
        siempre la migración.
        """
        huella = json.dumps(details.get("rates_bp"), sort_keys=True)
        ya = con.execute(
            "SELECT 1 FROM central_audit WHERE action=? AND target=? AND details_json LIKE ?",
            ("COMMISSION_PERIOD_RATE_SEED_SKIPPED", period, f'%"rates_bp": {huella}%')).fetchone()
        if ya:
            return
        self.audit(con, actor, "COMMISSION_PERIOD_RATE_SEED_SKIPPED", period, details=details)

    def _audit_seed_once(self, con, action, target, details):
        """Asienta una decisión de siembra una sola vez.

        La migración corre en cada apertura de la base. Sin esta guarda, un período descartado
        volvería a asentarse en cada arranque y la auditoría dejaría de poder leerse.
        """
        if con.execute("SELECT 1 FROM central_audit WHERE action=? AND target=?",
                       (action, target)).fetchone():
            return
        self.audit(con, "MIGRACION", action, target, details=details)

    def audit(self, con, actor, action, target, result="SUCCESS", details=None):
        con.execute(
            "INSERT INTO central_audit(actor,action,target,result,details_json,recorded_at) VALUES(?,?,?,?,?,?)",
            (actor, action, target, result, json.dumps(details or {}, ensure_ascii=False, sort_keys=True), datetime.now().astimezone().isoformat()),
        )

    def latest_snapshots(self) -> dict[Unit, sqlite3.Row]:
        with self.connection() as con:
            rows = con.execute("""
              SELECT s.* FROM cash_snapshots s JOIN (
                SELECT unit, MAX(source_updated_at) newest FROM cash_snapshots GROUP BY unit
              ) x ON x.unit=s.unit AND x.newest=s.source_updated_at
            """).fetchall()
        return {Unit(row["unit"]): row for row in rows}

    def alerts(self, active_only=True) -> list[Alert]:
        query = "SELECT * FROM central_alerts" + (" WHERE status='ACTIVE'" if active_only else "") + " ORDER BY created_at DESC"
        with self.connection() as con:
            rows = con.execute(query).fetchall()
        return [Alert(row["id"], Unit(row["unit"]), row["kind"], row["severity"], row["message"], row["status"], datetime.fromisoformat(row["created_at"]), row["acknowledged_by"]) for row in rows]

    def audit_log(self, limit=200):
        with self.connection() as con:
            return [dict(row) for row in con.execute("SELECT * FROM central_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
