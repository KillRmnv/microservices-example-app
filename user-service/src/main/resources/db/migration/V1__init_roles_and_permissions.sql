CREATE TABLE permissions
(
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE roles
(
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE role_permissions
(
    role_id       BIGINT NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions (id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Permissions (7 items)
INSERT INTO permissions (name)
VALUES ('CREATE_BOOKING'),
       ('READ_BOOKING'),
       ('CANCEL_BOOKING'),
       ('EVENT_CREATE'),
       ('EVENT_UPDATE'),
       ('USER_MANAGE'),
       ('ADMIN_BYPASS');

-- Roles (3 items)
INSERT INTO roles (name)
VALUES ('CUSTOMER'),
       ('EVENT_MANAGER'),
       ('ADMIN');

-- Role → Permission mapping

-- CUSTOMER: CREATE_BOOKING, CANCEL_BOOKING, READ_BOOKING
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'CUSTOMER'
  AND p.name IN ('CREATE_BOOKING', 'CANCEL_BOOKING', 'READ_BOOKING');

-- EVENT_MANAGER: EVENT_CREATE, EVENT_UPDATE, READ_BOOKING
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'EVENT_MANAGER'
  AND p.name IN ('EVENT_CREATE', 'EVENT_UPDATE', 'READ_BOOKING');

-- ADMIN: all 7 permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'ADMIN';
