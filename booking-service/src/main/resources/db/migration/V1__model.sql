CREATE TABLE towns
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE venues
(
    id       SERIAL PRIMARY KEY,
    town_id  INT          NOT NULL,
    place    VARCHAR(255) NOT NULL,
    capacity INT          NOT NULL check (capacity > 0),
    CONSTRAINT fk_venues_town
        FOREIGN KEY (town_id)
            REFERENCES towns (id)
            ON DELETE CASCADE
);

CREATE TABLE events
(
    id             SERIAL PRIMARY KEY,
    title          VARCHAR(255) NOT NULL,
    starts_at      TIMESTAMP    NOT NULL CHECK ( starts_at>CURRENT_TIMESTAMP ),
    ends_at        TIMESTAMP    NOT NULL CHECK ( ends_at>starts_at ),
    venue_id       INT          NOT NULL,
    admission_mode VARCHAR(50)  NOT NULL,
    CONSTRAINT fk_events_venue
        FOREIGN KEY (venue_id)
            REFERENCES venues (id)
            ON DELETE CASCADE,
    CONSTRAINT chk_events_admission_mode
        CHECK (admission_mode IN ('SEATABLE', 'GENERAL'))
);

CREATE TABLE seats
(
    id          SERIAL PRIMARY KEY,
    sector      VARCHAR(255) NOT NULL,
    row_label   VARCHAR(255) NOT NULL,
    seat_number VARCHAR(255) NOT NULL,
    venue_id    INT          NOT NULL,
    CONSTRAINT fk_seats_venue
        FOREIGN KEY (venue_id)
            REFERENCES venues (id)
            ON DELETE CASCADE
);

CREATE TABLE tickets
(
    id       SERIAL PRIMARY KEY,
    event_id INT            NOT NULL,
    zone     VARCHAR(50)    NOT NULL,
    price    DECIMAL(10, 2) NOT NULL CHECK ( price > 0 ),
    active   BOOLEAN        NOT NULL,
    user_id  INT,
    CONSTRAINT fk_tickets_event
        FOREIGN KEY (event_id)
            REFERENCES events (id)
            ON DELETE CASCADE,
    CONSTRAINT chk_tickets_zone
        CHECK (zone IN ('VIP', 'FAN_ZONE', 'BASIC'))
);

CREATE TABLE seatable_tickets
(
    ticket_id INT PRIMARY KEY,
    seat_id   INT NOT NULL,
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

    venue_id INT PRIMARY KEY,
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