-- Clear the tables the synthetic dataset repopulates, so a fixed-PK load doesn't collide with what is
-- already in the demo database. FK checks off for the truncate order.
--
-- TWO CLASSES OF DAMAGE this script used to cause, both of which broke the Open Dental CLIENT outright
-- (unhandled "Index was out of range" in ControlAppt.ModuleSelected on every launch, from 2026-07-27 until
-- it was diagnosed on 2026-07-30). Neither surfaced in Privara's own tests, because Privara only READS.
--
--   1. It TRUNCATEd `definition` wholesale. Open Dental ships ~296 definitions across 36 categories and the
--      generator repopulates only THREE of them (billing type, payment type, procedure category). The other
--      33 -- appointment confirmation statuses, appointment colours, recall types and so on -- were left
--      EMPTY, and the client indexes those lists directly, so an empty list at [0] threw. Now only the three
--      generated categories are cleared; everything else is left alone.
--
--   2. It truncated `operatory`, `provider` and `appointment` but NOT the tables that REFERENCE them:
--      `schedule`, `scheduleop`, `apptviewitem`. Those kept pointing at deleted primary keys -- 57,696
--      dangling rows in one measured case -- because the generator recreates operatories and providers with
--      NEW ids. They are cleared here too. The generator emits no provider schedules, so an empty
--      `schedule`/`scheduleop` is the correct end state; `apptview` itself is preserved, so the views
--      survive and simply lose their stale operatory columns until reconfigured in the client.
--
-- If you add a table to the generator, add it here AND check what references it.

SET FOREIGN_KEY_CHECKS = 0;

-- ---- tables the generator fully owns --------------------------------------------------------------
TRUNCATE TABLE allergy;
TRUNCATE TABLE allergydef;
TRUNCATE TABLE appointment;
TRUNCATE TABLE carrier;
TRUNCATE TABLE claimproc;
TRUNCATE TABLE commlog;
TRUNCATE TABLE disease;
TRUNCATE TABLE diseasedef;
TRUNCATE TABLE insplan;
TRUNCATE TABLE inssub;
TRUNCATE TABLE medication;
TRUNCATE TABLE medicationpat;
TRUNCATE TABLE operatory;
TRUNCATE TABLE patient;
TRUNCATE TABLE patplan;
TRUNCATE TABLE payment;
TRUNCATE TABLE paysplit;
TRUNCATE TABLE perioexam;
TRUNCATE TABLE periomeasure;
TRUNCATE TABLE procedurecode;
TRUNCATE TABLE procedurelog;
TRUNCATE TABLE procnote;
TRUNCATE TABLE provider;
TRUNCATE TABLE recall;

-- ---- definition: ONLY the categories the generator rewrites (see note 1) ---------------------------
--   4 = BillingType    10 = PaymentType    11 = ProcCodeCat
DELETE FROM definition WHERE Category IN (4, 10, 11);

-- ---- dependants of the tables above, which would otherwise dangle (see note 2) ---------------------
TRUNCATE TABLE schedule;
TRUNCATE TABLE scheduleop;
DELETE FROM apptviewitem WHERE OpNum <> 0 OR ProvNum <> 0;  -- keep the display-element rows

SET FOREIGN_KEY_CHECKS = 1;
