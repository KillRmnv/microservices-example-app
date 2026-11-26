CREATE TABLE towns
(
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE venues
(
    id       BIGSERIAL PRIMARY KEY,
    town_id  BIGINT       NOT NULL,
    place    VARCHAR(255) NOT NULL,
    capacity INT          NOT NULL check (capacity > 0),
    CONSTRAINT fk_venues_town
        FOREIGN KEY (town_id)
            REFERENCES towns (id)
            ON DELETE CASCADE
);

CREATE TABLE events
(
    id             BIGSERIAL PRIMARY KEY,
    title          VARCHAR(255) NOT NULL,
    starts_at      TIMESTAMP    NOT NULL CHECK ( starts_at>CURRENT_TIMESTAMP ),
    ends_at        TIMESTAMP    NOT NULL CHECK ( ends_at>starts_at ),
    venue_id       BIGINT       NOT NULL,
    category       VARCHAR(32)  NOT NULL DEFAULT 'other',
    admission_mode VARCHAR(50)  NOT NULL,
    CONSTRAINT fk_events_venue
        FOREIGN KEY (venue_id)
            REFERENCES venues (id)
            ON DELETE CASCADE,
    CONSTRAINT chk_events_admission_mode
        CHECK (admission_mode IN ('SEATABLE', 'GENERAL')),
    CONSTRAINT chk_events_category
        CHECK (category IN ('concert', 'theatre', 'exhibition',
                            'film', 'sport', 'kids', 'other'))
);

CREATE TABLE seats
(
    id          BIGSERIAL PRIMARY KEY,
    sector      VARCHAR(255) NOT NULL,
    row_label   VARCHAR(255) NOT NULL,
    seat_number VARCHAR(255) NOT NULL,
    venue_id    BIGINT       NOT NULL,
    CONSTRAINT fk_seats_venue
        FOREIGN KEY (venue_id)
            REFERENCES venues (id)
            ON DELETE CASCADE
);

CREATE TABLE tickets
(
    id       BIGSERIAL PRIMARY KEY,
    event_id BIGINT         NOT NULL,
    zone     VARCHAR(50)    NOT NULL,
    price    DECIMAL(10, 2) NOT NULL CHECK ( price > 0 ),
    active   BOOLEAN        NOT NULL,
    user_id  BIGINT,
    CONSTRAINT fk_tickets_event
        FOREIGN KEY (event_id)
            REFERENCES events (id)
            ON DELETE CASCADE,
    CONSTRAINT chk_tickets_zone
        CHECK (zone IN ('VIP', 'FAN_ZONE', 'BASIC'))
);

CREATE TABLE seatable_tickets
(
    ticket_id BIGINT PRIMARY KEY,
    seat_id   BIGINT NOT NULL,
    CONSTRAINT fk_seatable_tickets_ticket
        FOREIGN KEY (ticket_id)
            REFERENCES tickets (id)
            ON DELETE CASCADE,
    CONSTRAINT fk_seatable_tickets_seat
        FOREIGN KEY (seat_id)
            REFERENCES seats (id)
            ON DELETE CASCADE
);
CREATE TABLE venue_fullness
(

    venue_id BIGINT PRIMARY KEY,
    fullness INT CHECK ( fullness > 0 ),
    CONSTRAINT fk_venue
        FOREIGN KEY (venue_id)
            REFERENCES venues (id)
                ON DELETE CASCADE
);
CREATE INDEX idx_venues_town_id ON venues (town_id);
CREATE INDEX idx_events_venue_id ON events (venue_id);
CREATE INDEX idx_seats_venue_id ON seats (venue_id);
CREATE INDEX idx_tickets_event_id ON tickets (event_id);
CREATE INDEX idx_tickets_user_id ON tickets (user_id);
CREATE INDEX idx_seatable_tickets_seat_id ON seatable_tickets (seat_id);

CREATE UNIQUE INDEX uq_seats_venue_sector_row_number
    ON seats (venue_id, sector, row_label, seat_number);


CREATE OR REPLACE FUNCTION chk_venue_capacity()
    RETURNS trigger AS

$$
    DECLARE
        fullness_var int;
        venue_id_var int;
        capacity_var int;
BEGIN
    SELECT vf.fullness,vf.venue_id INTO fullness_var,venue_id_var FROM events e JOIN venue_fullness vf ON e.venue_id=vf.venue_id  WHERE NEW.event_id=e.id;
    SELECT venues.capacity INTO capacity_var FROM venues WHERE id=venue_id_var;
    fullness_var:=fullness_var+1;
    IF fullness_var > capacity_var THEN
        RAISE EXCEPTION 'Venue is full for this event';
    ELSE
        UPDATE venue_fullness SET fullness = fullness_var WHERE venue_id = venue_id_var;
    end if;
    RETURN NEW;

end;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER check_venue_fullness
    BEFORE UPDATE ON tickets FOR EACH ROW
    EXECUTE FUNCTION chk_venue_capacity();

-- ---------------------------------------------------------------- seed

-- Towns
INSERT INTO towns (name)
VALUES ('Minsk'),
       ('Grodno'),
       ('Brest')
ON CONFLICT (name) DO NOTHING;

INSERT INTO venues (town_id, place, capacity)
SELECT t.id, v.place, v.capacity
FROM (
         VALUES
             ('Minsk', 'Minsk Arena', 15000),
             ('Minsk', 'Prime Hall', 2000),
             ('Grodno', 'Grodno Concert Hall', 3500),
             ('Brest', 'Brest Sports Palace', 5000)
     ) AS v(town_name, place, capacity)
         JOIN towns t ON t.name = v.town_name
WHERE NOT EXISTS (
    SELECT 1
    FROM venues existing
    WHERE existing.place = v.place
);

INSERT INTO events (title, starts_at, ends_at, venue_id, category, admission_mode)
SELECT e.title,
       CURRENT_TIMESTAMP + e.start_offset,
       CURRENT_TIMESTAMP + e.end_offset,
       v.id,
       e.category,
       e.admission_mode
FROM (
         VALUES
             ('Imagine Dragons Tribute', INTERVAL '3 days', INTERVAL '3 days 3 hours', 'Minsk Arena', 'concert', 'SEATABLE'),
             ('UFC Public Screening', INTERVAL '5 days', INTERVAL '5 days 4 hours', 'Prime Hall', 'sport', 'GENERAL'),
             ('Symphonic Anime Night', INTERVAL '7 days', INTERVAL '7 days 2 hours 30 minutes', 'Grodno Concert Hall', 'concert', 'SEATABLE'),
             ('Stand-up Festival', INTERVAL '10 days', INTERVAL '10 days 2 hours', 'Brest Sports Palace', 'concert', 'GENERAL')
     ) AS e(title, start_offset, end_offset, venue_place, category, admission_mode)
         JOIN venues v ON v.place = e.venue_place
WHERE NOT EXISTS (
    SELECT 1
    FROM events existing
    WHERE existing.title = e.title
);

INSERT INTO seats (sector, row_label, seat_number, venue_id)
SELECT s.sector, s.row_label, s.seat_number, v.id
FROM (
         VALUES
             ('A', '1', '1'),
             ('A', '1', '2'),
             ('A', '1', '3'),
             ('A', '2', '1'),
             ('A', '2', '2'),
             ('VIP', '1', '1'),
             ('VIP', '1', '2'),
             ('VIP', '1', '3')
     ) AS s(sector, row_label, seat_number)
         JOIN venues v ON v.place = 'Minsk Arena'
WHERE NOT EXISTS (
    SELECT 1
    FROM seats existing
    WHERE existing.venue_id = v.id
      AND existing.sector = s.sector
      AND existing.row_label = s.row_label
      AND existing.seat_number = s.seat_number
);

INSERT INTO seats (sector, row_label, seat_number, venue_id)
SELECT s.sector, s.row_label, s.seat_number, v.id
FROM (
         VALUES
             ('Parterre', '1', '1'),
             ('Parterre', '1', '2'),
             ('Parterre', '1', '3'),
             ('Balcony', '1', '1'),
             ('Balcony', '1', '2')
     ) AS s(sector, row_label, seat_number)
         JOIN venues v ON v.place = 'Grodno Concert Hall'
WHERE NOT EXISTS (
    SELECT 1
    FROM seats existing
    WHERE existing.venue_id = v.id
      AND existing.sector = s.sector
      AND existing.row_label = s.row_label
      AND existing.seat_number = s.seat_number
);

INSERT INTO tickets (event_id, zone, price, active, user_id)
SELECT e.id, x.zone, x.price, TRUE, NULL
FROM (
         VALUES
             ('UFC Public Screening', 'VIP', 120.00),
             ('UFC Public Screening', 'FAN_ZONE', 80.00),
             ('UFC Public Screening', 'BASIC', 50.00),
             ('Stand-up Festival', 'VIP', 100.00),
             ('Stand-up Festival', 'FAN_ZONE', 65.00),
             ('Stand-up Festival', 'BASIC', 40.00)
     ) AS x(event_title, zone, price)
         JOIN events e ON e.title = x.event_title
WHERE NOT EXISTS (
    SELECT 1
    FROM tickets t
    WHERE t.event_id = e.id
      AND t.zone = x.zone
      AND t.price = x.price
      AND t.user_id IS NULL
);

INSERT INTO tickets (event_id, zone, price, active, user_id)
SELECT e.id,
       CASE
           WHEN s.sector = 'VIP' THEN 'VIP'
           WHEN s.sector = 'A' THEN 'FAN_ZONE'
           ELSE 'BASIC'
           END,
       CASE
           WHEN s.sector = 'VIP' THEN 250.00
           WHEN s.sector = 'A' THEN 150.00
           ELSE 90.00
           END,
       TRUE,
       NULL
FROM events e
         JOIN venues v ON v.id = e.venue_id
         JOIN seats s ON s.venue_id = v.id
WHERE e.title = 'Imagine Dragons Tribute'
  AND v.place = 'Minsk Arena'
  AND NOT EXISTS (
    SELECT 1
    FROM tickets t
             JOIN seatable_tickets st ON st.ticket_id = t.id
    WHERE t.event_id = e.id
      AND st.seat_id = s.id
);

INSERT INTO seatable_tickets (ticket_id, seat_id)
SELECT t.id, s.id
FROM events e
         JOIN venues v ON v.id = e.venue_id
         JOIN seats s ON s.venue_id = v.id
         JOIN tickets t ON t.event_id = e.id
    AND t.zone = CASE
                     WHEN s.sector = 'VIP' THEN 'VIP'
                     WHEN s.sector = 'A' THEN 'FAN_ZONE'
                     ELSE 'BASIC'
        END
    AND t.price = CASE
                      WHEN s.sector = 'VIP' THEN 250.00
                      WHEN s.sector = 'A' THEN 150.00
                      ELSE 90.00
        END
WHERE e.title = 'Imagine Dragons Tribute'
  AND v.place = 'Minsk Arena'
ON CONFLICT (ticket_id) DO NOTHING;

INSERT INTO tickets (event_id, zone, price, active, user_id)
SELECT e.id,
       CASE
           WHEN s.sector = 'Parterre' THEN 'VIP'
           ELSE 'BASIC'
           END,
       CASE
           WHEN s.sector = 'Parterre' THEN 130.00
           ELSE 75.00
           END,
       TRUE,
       NULL
FROM events e
         JOIN venues v ON v.id = e.venue_id
         JOIN seats s ON s.venue_id = v.id
WHERE e.title = 'Symphonic Anime Night'
  AND v.place = 'Grodno Concert Hall'
  AND NOT EXISTS (
    SELECT 1
    FROM tickets t
             JOIN seatable_tickets st ON st.ticket_id = t.id
    WHERE t.event_id = e.id
      AND st.seat_id = s.id
);

INSERT INTO seatable_tickets (ticket_id, seat_id)
SELECT t.id, s.id
FROM events e
         JOIN venues v ON v.id = e.venue_id
         JOIN seats s ON s.venue_id = v.id
         JOIN tickets t ON t.event_id = e.id
    AND t.zone = CASE
                     WHEN s.sector = 'Parterre' THEN 'VIP'
                     ELSE 'BASIC'
        END
    AND t.price = CASE
                      WHEN s.sector = 'Parterre' THEN 130.00
                      ELSE 75.00
        END
WHERE e.title = 'Symphonic Anime Night'
  AND v.place = 'Grodno Concert Hall'
ON CONFLICT (ticket_id) DO NOTHING;