-- Curry Takeaway Ordering System — schema v1.1
-- PostgreSQL 16. Companion to Curry_Takeaway_Ordering_System_Spec_v1.1.md (§7, §8).
-- Runtime source of truth is Django migrations; this file is the reference DDL
-- and is executed in CI against an empty database to prove it loads.

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- enums
CREATE TYPE user_role           AS ENUM ('owner', 'manager');
CREATE TYPE order_source        AS ENUM ('website', 'whatsapp_assisted', 'phone', 'in_person');
CREATE TYPE order_status        AS ENUM (
  'awaiting_eft', 'payment_review', 'confirmed_prep',
  'cash_request', 'cash_due',
  'in_kitchen', 'ready', 'collected',
  'payment_expired', 'cancelled');
CREATE TYPE payment_method      AS ENUM ('eft', 'cash');
CREATE TYPE payment_status      AS ENUM (
  'pending', 'under_review', 'verified', 'rejected', 'expired', 'collected_cash', 'cancelled');
CREATE TYPE cancellation_reason AS ENUM (
  'customer_request', 'staff', 'cash_rejected', 'payment_rejected',
  'no_show', 'day_closed', 'duplicate', 'owner_exception', 'other');
CREATE TYPE actor_kind          AS ENUM ('staff', 'customer', 'system');
CREATE TYPE media_kind          AS ENUM ('proof', 'dish_image');

-- ---------------------------------------------------------------- staff
CREATE TABLE users (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email                 citext NOT NULL UNIQUE,
  name                  text   NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  role                  user_role NOT NULL,
  password_hash         text   NOT NULL,
  active                boolean NOT NULL DEFAULT true,
  must_change_password  boolean NOT NULL DEFAULT true,
  failed_login_count    smallint NOT NULL DEFAULT 0,
  locked_until          timestamptz,
  last_login_at         timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- settings (single row)
CREATE TABLE settings (
  id                             smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  public_site_name               text NOT NULL,
  collection_address_line        text,
  collection_instructions        text,
  bank_name                      text,
  account_name                   text,
  account_number                 text CHECK (account_number ~ '^[0-9]{6,20}$'),
  branch_code                    text,
  account_type                   text,
  default_window_start           time NOT NULL DEFAULT '16:00',
  default_window_end             time NOT NULL DEFAULT '18:00',
  slot_minutes                   smallint NOT NULL DEFAULT 15 CHECK (slot_minutes BETWEEN 5 AND 60),
  default_slot_capacity          smallint NOT NULL DEFAULT 13 CHECK (default_slot_capacity >= 1),
  default_daily_order_cap        smallint NOT NULL DEFAULT 100 CHECK (default_daily_order_cap >= 1),
  same_day_cutoff                time NOT NULL DEFAULT '10:00',
  preorder_days                  smallint NOT NULL DEFAULT 7 CHECK (preorder_days BETWEEN 0 AND 14),
  eft_hold_minutes               smallint NOT NULL DEFAULT 30 CHECK (eft_hold_minutes BETWEEN 5 AND 120),
  max_hold_extensions            smallint NOT NULL DEFAULT 1 CHECK (max_hold_extensions BETWEEN 0 AND 3),
  hold_extension_minutes         smallint NOT NULL DEFAULT 15 CHECK (hold_extension_minutes BETWEEN 5 AND 60),
  payment_review_sla_minutes     smallint NOT NULL DEFAULT 15 CHECK (payment_review_sla_minutes BETWEEN 5 AND 120),
  cash_enabled                   boolean NOT NULL DEFAULT true,
  cash_same_day_only             boolean NOT NULL DEFAULT true,
  cash_daily_cap                 smallint NOT NULL DEFAULT 20 CHECK (cash_daily_cap >= 0),
  collection_grace_minutes       smallint NOT NULL DEFAULT 15 CHECK (collection_grace_minutes BETWEEN 0 AND 60),
  assisted_after_cutoff_enabled  boolean NOT NULL DEFAULT false,
  support_whatsapp_e164          text CHECK (support_whatsapp_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  allergen_disclaimer            text,
  home_kitchen_notice            text,
  vat_registered                 boolean NOT NULL DEFAULT false,
  vat_number                     text,
  proof_retention_days           smallint NOT NULL DEFAULT 90 CHECK (proof_retention_days BETWEEN 30 AND 365),
  order_retention_months         smallint NOT NULL DEFAULT 18 CHECK (order_retention_months BETWEEN 6 AND 60),
  sms_enabled                    boolean NOT NULL DEFAULT false,
  sms_ready_template             text NOT NULL DEFAULT '{site}: order {order_number} is ready. Collect {slot_label} at {address_line}. {instructions}',
  updated_by                     bigint REFERENCES users(id),
  updated_at                     timestamptz NOT NULL DEFAULT now(),
  CHECK (default_window_start < default_window_end),
  CHECK (same_day_cutoff < default_window_start),
  CHECK (cash_daily_cap <= default_daily_order_cap),
  CHECK (NOT vat_registered OR vat_number IS NOT NULL)
);

CREATE TABLE settings_events (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     bigint REFERENCES users(id),
  diff        jsonb NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- media
CREATE TABLE media (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind         media_kind NOT NULL,
  storage_key  text NOT NULL UNIQUE,
  mime_type    text NOT NULL,
  byte_size    integer NOT NULL CHECK (byte_size > 0 AND byte_size <= 8 * 1024 * 1024),
  sha256       bytea NOT NULL,
  order_id     bigint,            -- FK added after orders exists
  dish_id      bigint,            -- FK added after dishes exists
  uploaded_by  bigint REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  purged_at    timestamptz,
  CHECK (kind <> 'proof'      OR mime_type IN ('image/jpeg','image/png','image/webp','application/pdf')),
  CHECK (kind <> 'dish_image' OR mime_type IN ('image/jpeg','image/png','image/webp'))
);

-- ---------------------------------------------------------------- menu
CREATE TABLE dishes (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug               text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name               text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  short_description  text,
  long_description   text,
  price_cents        integer NOT NULL CHECK (price_cents >= 0),
  portion_label      text,
  spice_default      text,
  allergen_text      text,
  dietary_tags       text[] NOT NULL DEFAULT '{}',
  image_media_id     bigint REFERENCES media(id),
  image_alt          text,
  category           text,
  sort_order         integer NOT NULL DEFAULT 0,
  is_active_on_menu  boolean NOT NULL DEFAULT false,
  allow_notes        boolean NOT NULL DEFAULT true,
  archived_at        timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE media ADD CONSTRAINT media_dish_fk FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE SET NULL;

CREATE TABLE dish_options (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dish_id    bigint NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  name       text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
  required   boolean NOT NULL DEFAULT true,
  sort_order integer NOT NULL DEFAULT 0,
  UNIQUE (dish_id, name)
);

CREATE TABLE dish_option_values (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  option_id         bigint NOT NULL REFERENCES dish_options(id) ON DELETE CASCADE,
  name              text NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
  price_delta_cents integer NOT NULL DEFAULT 0,
  sort_order        integer NOT NULL DEFAULT 0,
  is_available      boolean NOT NULL DEFAULT true,
  UNIQUE (option_id, name)
);

-- ---------------------------------------------------------------- trading calendar
CREATE TABLE trading_days (
  date               date PRIMARY KEY,                 -- SAST calendar date
  is_open            boolean NOT NULL DEFAULT true,
  window_start       time NOT NULL,
  window_end         time NOT NULL,
  cutoff_time        time NOT NULL,
  daily_order_cap    smallint NOT NULL CHECK (daily_order_cap >= 0),
  next_order_seq     integer NOT NULL DEFAULT 1 CHECK (next_order_seq BETWEEN 1 AND 10000),
  kitchen_locked_at  timestamptz,
  kitchen_locked_by  bigint REFERENCES users(id),
  closed_out_at      timestamptz,
  closed_out_by      bigint REFERENCES users(id),
  notes_internal     text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (window_start < window_end)
);

CREATE TABLE slots (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  trading_day date NOT NULL REFERENCES trading_days(date) ON DELETE CASCADE,
  start_at    time NOT NULL,
  end_at      time NOT NULL,
  capacity    smallint NOT NULL CHECK (capacity >= 0),
  is_closed   boolean NOT NULL DEFAULT false,
  UNIQUE (trading_day, start_at),
  CHECK (start_at < end_at)
);

CREATE TABLE day_dish_availability (
  trading_day  date   NOT NULL REFERENCES trading_days(date) ON DELETE CASCADE,
  dish_id      bigint NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
  is_available boolean NOT NULL DEFAULT true,
  max_units    integer CHECK (max_units IS NULL OR max_units >= 0),
  PRIMARY KEY (trading_day, dish_id)
);

-- ---------------------------------------------------------------- customers & orders
CREATE TABLE customers (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  full_name      text NOT NULL CHECK (length(full_name) BETWEEN 2 AND 80),
  mobile_e164    text NOT NULL UNIQUE CHECK (mobile_e164 ~ '^\+27[6-8][0-9]{8}$'),
  first_seen_at  timestamptz NOT NULL DEFAULT now(),
  last_order_at  timestamptz,
  order_count    integer NOT NULL DEFAULT 0,
  anonymised_at  timestamptz
);

CREATE TABLE orders (
  id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_number              text NOT NULL UNIQUE CHECK (order_number ~ '^CT-[0-9]{6}-[0-9]{4}$'),
  public_token              text NOT NULL UNIQUE CHECK (length(public_token) >= 22),
  source                    order_source NOT NULL,
  customer_id               bigint REFERENCES customers(id) ON DELETE SET NULL,
  customer_name_snapshot    text NOT NULL,
  customer_mobile_snapshot  text NOT NULL,
  note                      text CHECK (note IS NULL OR length(note) <= 200),
  trading_day               date NOT NULL REFERENCES trading_days(date),
  slot_id                   bigint NOT NULL REFERENCES slots(id),
  status                    order_status NOT NULL,
  payment_method            payment_method NOT NULL,
  subtotal_cents            integer NOT NULL CHECK (subtotal_cents >= 0),
  discount_cents            integer NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
  total_cents               integer NOT NULL CHECK (total_cents >= 0),
  balance_due_cents         integer NOT NULL DEFAULT 0 CHECK (balance_due_cents >= 0),
  refund_note               text,
  hold_expires_at           timestamptz,
  hold_extensions           smallint NOT NULL DEFAULT 0 CHECK (hold_extensions >= 0),
  dish_units_consumed       boolean NOT NULL DEFAULT false,
  dispute_flag              boolean NOT NULL DEFAULT false,
  after_cutoff_reason       text,
  assigned_user_id          bigint REFERENCES users(id),
  cancellation_reason       cancellation_reason,
  cancellation_note         text,
  created_by_user_id        bigint REFERENCES users(id),   -- null for website
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now(),
  confirmed_at              timestamptz,
  in_kitchen_at             timestamptz,
  ready_at                  timestamptz,
  collected_at              timestamptz,
  cancelled_at              timestamptz,
  CHECK (total_cents = subtotal_cents - discount_cents),
  CHECK (status <> 'cancelled' OR cancellation_reason IS NOT NULL),
  CHECK (status <> 'awaiting_eft' OR hold_expires_at IS NOT NULL),
  CHECK (payment_method = 'eft' OR hold_expires_at IS NULL),
  CHECK (NOT dish_units_consumed OR in_kitchen_at IS NOT NULL)
);
ALTER TABLE media ADD CONSTRAINT media_order_fk FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE;

CREATE INDEX orders_day_status_idx     ON orders (trading_day, status);
CREATE INDEX orders_slot_status_idx    ON orders (slot_id, status);
CREATE INDEX orders_hold_idx           ON orders (hold_expires_at) WHERE status = 'awaiting_eft';
CREATE INDEX orders_mobile_idx         ON orders (customer_mobile_snapshot);
CREATE INDEX orders_customer_idx       ON orders (customer_id);
CREATE INDEX orders_created_idx        ON orders (created_at);

CREATE TABLE order_lines (
  id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id                  bigint NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  dish_id                   bigint REFERENCES dishes(id) ON DELETE SET NULL,
  dish_name_snapshot        text NOT NULL,
  unit_price_cents_snapshot integer NOT NULL CHECK (unit_price_cents_snapshot >= 0),
  quantity                  integer NOT NULL CHECK (quantity BETWEEN 1 AND 20),
  options_snapshot          jsonb NOT NULL DEFAULT '[]'::jsonb,
  -- "Spice=Mild|Starch=Rice", options sorted by name; used for kitchen grouping
  option_key                text NOT NULL DEFAULT '',
  line_total_cents          integer NOT NULL CHECK (line_total_cents >= 0),
  kitchen_note              text CHECK (kitchen_note IS NULL OR length(kitchen_note) <= 200),
  CHECK (jsonb_typeof(options_snapshot) = 'array')
);
CREATE INDEX order_lines_order_idx ON order_lines (order_id);
CREATE INDEX order_lines_dish_idx  ON order_lines (dish_id);

CREATE TABLE payments (
  id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id                    bigint NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
  method                      payment_method NOT NULL,
  amount_cents                integer NOT NULL CHECK (amount_cents >= 0),
  reference                   text NOT NULL,
  current_proof_media_id      bigint REFERENCES media(id),
  customer_declared_ref       text,
  proof_uploaded_at           timestamptz,
  status                      payment_status NOT NULL DEFAULT 'pending',
  verified_by                 bigint REFERENCES users(id),
  verified_at                 timestamptz,
  rejected_reason             text,
  cash_received_by            bigint REFERENCES users(id),
  cash_received_at            timestamptz,
  cash_amount_received_cents  integer CHECK (cash_amount_received_cents IS NULL OR cash_amount_received_cents >= 0),
  CHECK (status <> 'verified'       OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)),
  CHECK (status <> 'collected_cash' OR (cash_received_by IS NOT NULL AND cash_received_at IS NOT NULL AND cash_amount_received_cents IS NOT NULL))
);

CREATE TABLE order_events (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id       bigint NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  from_status    order_status,
  to_status      order_status,
  action         text NOT NULL,
  actor_kind     actor_kind NOT NULL,
  actor_user_id  bigint REFERENCES users(id),
  payload        jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (actor_kind <> 'staff' OR actor_user_id IS NOT NULL)
);
CREATE INDEX order_events_order_idx ON order_events (order_id, occurred_at);

-- ---------------------------------------------------------------- infrastructure tables
CREATE TABLE idempotency_keys (
  key             text PRIMARY KEY,
  request_sha256  bytea NOT NULL,
  order_id        bigint REFERENCES orders(id) ON DELETE CASCADE,
  response_status smallint NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idempotency_keys_created_idx ON idempotency_keys (created_at);

CREATE TABLE throttle_events (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scope       text NOT NULL,     -- checkout_ip | proof_token | lookup_ip | lookup_order | login_email
  key         text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX throttle_events_lookup_idx ON throttle_events (scope, key, occurred_at);

CREATE TABLE job_heartbeats (
  job_name    text PRIMARY KEY,
  last_run_at timestamptz NOT NULL,
  last_ok     boolean NOT NULL,
  detail      text
);

-- ---------------------------------------------------------------- capacity views (§8.1)
CREATE VIEW v_occupying_orders AS
SELECT *
  FROM orders
 WHERE status IN ('awaiting_eft','payment_review','cash_request',
                  'confirmed_prep','cash_due','in_kitchen','ready');

CREATE VIEW v_day_occupancy AS
SELECT trading_day,
       count(*)                                       AS orders_occupying,
       count(*) FILTER (WHERE payment_method = 'cash') AS cash_occupying
  FROM v_occupying_orders
 GROUP BY trading_day;

CREATE VIEW v_slot_occupancy AS
SELECT s.id AS slot_id, s.trading_day, s.start_at, s.end_at, s.capacity, s.is_closed,
       count(o.id) AS orders_occupying,
       s.capacity - count(o.id) AS remaining
  FROM slots s
  LEFT JOIN v_occupying_orders o ON o.slot_id = s.id
 GROUP BY s.id;

CREATE VIEW v_dish_units_used AS
SELECT o.trading_day, l.dish_id, sum(l.quantity)::integer AS units
  FROM orders o
  JOIN order_lines l ON l.order_id = o.id
 WHERE l.dish_id IS NOT NULL
   AND (o.status IN ('awaiting_eft','payment_review','cash_request',
                     'confirmed_prep','cash_due','in_kitchen','ready')
        OR o.dish_units_consumed)
 GROUP BY o.trading_day, l.dish_id;

-- Kitchen board membership (§9.2 / §12.4)
CREATE VIEW v_kitchen_summary AS
SELECT o.trading_day, l.dish_name_snapshot, l.option_key,
       sum(l.quantity)::integer AS units,
       count(DISTINCT o.id)     AS orders
  FROM orders o
  JOIN order_lines l ON l.order_id = o.id
 WHERE o.status IN ('confirmed_prep','cash_due','in_kitchen','ready')
 GROUP BY o.trading_day, l.dish_name_snapshot, l.option_key;

-- ---------------------------------------------------------------- order number helper (§8.3 / D-04)
-- Call inside the reservation transaction AFTER the trading_days row is locked FOR UPDATE.
CREATE FUNCTION next_order_number(p_day date) RETURNS text
LANGUAGE plpgsql AS $$
DECLARE v_seq integer;
BEGIN
  UPDATE trading_days
     SET next_order_seq = next_order_seq + 1, updated_at = now()
   WHERE date = p_day
   RETURNING next_order_seq - 1 INTO v_seq;
  IF v_seq IS NULL THEN RAISE EXCEPTION 'trading day % not materialised', p_day; END IF;
  IF v_seq > 9999 THEN RAISE EXCEPTION 'order sequence exhausted for %', p_day; END IF;
  RETURN format('CT-%s-%s', to_char(p_day, 'YYMMDD'), lpad(v_seq::text, 4, '0'));
END $$;

-- ---------------------------------------------------------------- updated_at maintenance
CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;
CREATE TRIGGER dishes_touch       BEFORE UPDATE ON dishes       FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER orders_touch       BEFORE UPDATE ON orders       FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trading_days_touch BEFORE UPDATE ON trading_days FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

COMMIT;
