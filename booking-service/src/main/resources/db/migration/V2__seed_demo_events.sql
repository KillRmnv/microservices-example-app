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

INSERT INTO events (title, starts_at, ends_at, venue_id, admission_mode)
SELECT e.title,
       CURRENT_TIMESTAMP + e.start_offset,
       CURRENT_TIMESTAMP + e.end_offset,
       v.id,
       e.admission_mode
FROM (
         VALUES
             ('Imagine Dragons Tribute', INTERVAL '3 days', INTERVAL '3 days 3 hours', 'Minsk Arena', 'SEATABLE'),
             ('UFC Public Screening', INTERVAL '5 days', INTERVAL '5 days 4 hours', 'Prime Hall', 'GENERAL'),
             ('Symphonic Anime Night', INTERVAL '7 days', INTERVAL '7 days 2 hours 30 minutes', 'Grodno Concert Hall', 'SEATABLE'),
             ('Stand-up Festival', INTERVAL '10 days', INTERVAL '10 days 2 hours', 'Brest Sports Palace', 'GENERAL')
     ) AS e(title, start_offset, end_offset, venue_place, admission_mode)
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